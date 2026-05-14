import os
import uuid
from typing import Annotated, Any, Dict, List, Optional, Tuple, TypedDict, cast

from dotenv import load_dotenv
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field

load_dotenv(override=True)


class State(TypedDict):
    messages: Annotated[List[Any], add_messages]
    success_criteria: str
    feedback_on_work: Optional[str]
    success_criteria_met: bool
    user_input_needed: bool


class EvaluatorOutput(BaseModel):
    feedback: str = Field(description="Feedback on the assistant's response")
    success_criteria_met: bool = Field(
        description="Whether the success criteria have been met"
    )
    user_input_needed: bool = Field(
        description=(
            "True if more input is needed from the user, or clarifications, "
            "or the assistant is stuck"
        )
    )


class DocAnalyzerAgent:
    """
    Initialize the agent and its dependencies.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._agent_id = str(uuid.uuid4())

        self._model = model if model else os.getenv("LLM_MODEL", "llama3.2")
        self._provider = provider if provider else os.getenv("LLM_PROVIDER", "ollama")

    async def initialize(self) -> None:
        """
        Initialize the agent and its dependencies.
        """

        worker_llm: BaseChatModel
        evaluator_llm: BaseChatModel
        if self._provider == "ollama":
            worker_llm = ChatOllama(model=self._model)
            evaluator_llm = ChatOllama(model=self._model)
        elif self._provider == "openai":
            worker_llm = ChatOpenAI(model=self._model, temperature=0.3)
            evaluator_llm = ChatOpenAI(model=self._model, temperature=0.3)
        else:
            raise ValueError(f"Unsupported LLM provider: {self._provider}")

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True
        )

        toolkit = PlayWrightBrowserToolkit.from_browser(
            async_browser=self.browser
        )
        self._tools = toolkit.get_tools()

        self._worker_llm_with_tools = worker_llm.bind_tools(self._tools)
        self._evaluator_llm_with_output = evaluator_llm.with_structured_output(
            EvaluatorOutput
        )

        self._graph = self._build_graph()

    async def process_message(
        self,
        message: str,
        success_criteria: str,
        history: List[Any],
        thread: str,
    ) -> List[Dict[str, Any]]:
        """
        Process a message and return the response from the agent.

        Args:
            message: The message to process
            success_criteria: The success criteria for the message
            history: The history of the conversation
            thread: The thread ID

        Returns:
            The response from the agent with the user, reply and feedback.
        """

        config = {"configurable": {"thread_id": thread}}

        history = history[:50]

        state: State = {
            "messages": history + [HumanMessage(content=message)],
            "success_criteria": success_criteria,
            "feedback_on_work": None,
            "success_criteria_met": False,
            "user_input_needed": False,
        }

        result = await self._graph.ainvoke(state, config=config)

        user = {"role": "user", "content": message}
        reply = {"role": "assistant", "content": result["messages"][-2].content}
        feedback = {"role": "assistant", "content": result["messages"][-1].content}

        return [user, reply, feedback]

    async def reset(self) -> Tuple[str, str, Optional[str], str]:
        return "", "", None, self._make_thread_id()

    @staticmethod
    def _make_thread_id() -> str:
        return str(uuid.uuid4())

    def _build_graph(self) -> Any:
        graph_builder = StateGraph(State)

        graph_builder.add_node("worker", self._worker)
        graph_builder.add_node("tools", ToolNode(tools=self._tools))
        graph_builder.add_node("evaluator", self._evaluator)

        graph_builder.add_conditional_edges(
            "worker",
            self._worker_router,
            {"tools": "tools", "evaluator": "evaluator"},
        )
        graph_builder.add_edge("tools", "worker")
        graph_builder.add_conditional_edges(
            "evaluator",
            self._route_based_on_evaluation,
            {"worker": "worker", "END": END},
        )
        graph_builder.add_edge(START, "worker")

        memory = MemorySaver()
        graph = graph_builder.compile(checkpointer=memory)

        with open("graph.png", "wb") as f:
            f.write(graph.get_graph().draw_mermaid_png())

        return graph

    def _worker(self, state: State) -> Dict[str, Any]:
        system_message = f"""
You are a helpful assistant that can use tools to complete tasks.
To find information, you can use the following tools:
{self._tools}

Use the tools to find the information you need to answer the user's question.

You keep working on a task until either you have a question or clarification for the user,
or the success criteria is met.

This is the success criteria:
{state['success_criteria']}

You should reply either with a question for the user about this assignment,
or with your final response.
If you have a question for the user, you need to reply by clearly stating your question.
An example might be:

Question: please clarify whether you want a summary or a detailed answer

If you've finished, reply with the final answer, and don't ask a question;
simply reply with the answer.
"""

        if state.get("feedback_on_work"):
            system_message += f"""
Previously you thought you completed the assignment, but your reply was rejected
because the success criteria was not met.

Here is the feedback on why this was rejected:
{state['feedback_on_work']}

With this feedback, please continue the assignment, ensuring that you meet the
success criteria or have a question for the user.
"""

        found_system_message = False
        messages = state["messages"]
        for message in messages:
            if isinstance(message, SystemMessage):
                message.content = system_message
                found_system_message = True

        if not found_system_message:
            messages = [SystemMessage(content=system_message)] + messages

        response = self._worker_llm_with_tools.invoke(messages)

        return {
            "messages": [response],
        }

    def _worker_router(self, state: State) -> str:
        last_message = state["messages"][-1]

        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        else:
            return "evaluator"

    def _format_conversation(self, messages: List[Any]) -> str:
        conversation = "Conversation history:\n\n"
        for message in messages:
            if isinstance(message, HumanMessage):
                conversation += f"User: {message.content}\n"
            elif isinstance(message, AIMessage):
                text = message.content or "[Tools use]"
                conversation += f"Assistant: {text}\n"
        return conversation

    def _evaluator(self, state: State) -> Dict[str, Any]:
        last_response = state["messages"][-1].content

        system_message = """
You are an evaluator that determines if a task has been completed successfully by an Assistant.
Assess the Assistant's last response based on the given criteria. Respond with your feedback,
and with your decision on whether the success criteria has been met,
and whether more input is needed from the user.
"""

        user_message = f"""
You are evaluating a conversation between the User and Assistant.
You decide what action to take based on the last response from the Assistant.

The entire conversation with the assistant, with the user's original request and all replies,
is:
{self._format_conversation(state['messages'])}

The success criteria for this assignment is:
{state['success_criteria']}

And the final response from the Assistant that you are evaluating is:
{last_response}

Respond with your feedback, and decide if the success criteria is met by this response.
Also, decide if more user input is required, either because the assistant has a question,
needs clarification, or seems to be stuck and unable to answer without help.
"""

        if state["feedback_on_work"]:
            user_message += (
                "Also, note that in a prior attempt from the Assistant, "
                f"you provided this feedback: {state['feedback_on_work']}\n"
            )
            user_message += (
                "If you're seeing the Assistant repeating the same mistakes, "
                "then consider responding that user input is required."
            )

        evaluator_messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_message),
        ]

        eval_result = cast(
            EvaluatorOutput,
            self._evaluator_llm_with_output.invoke(evaluator_messages),
        )

        new_state: Dict[str, Any] = {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        f"Evaluator Feedback on this answer: {eval_result.feedback}"
                    ),
                }
            ],
            "feedback_on_work": eval_result.feedback,
            "success_criteria_met": eval_result.success_criteria_met,
            "user_input_needed": eval_result.user_input_needed,
        }
        return new_state

    def _route_based_on_evaluation(self, state: State) -> str:
        if state["success_criteria_met"] or state["user_input_needed"]:
            return "END"
        else:
            return "worker"
