import os
import uuid
import logging
from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict, cast
from dotenv import load_dotenv
from chromadb import PersistentClient
from chromadb.api import ClientAPI
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from playwright.async_api import async_playwright
from pydantic import BaseModel

from agents.doc_analyzer_prompts import (
    EvaluatorOutput,
    get_websearch_evaluator_background,
    get_websearch_evaluator_prompt,
    get_websearch_searcher_prompt,
)

load_dotenv(override=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class State(TypedDict):
    messages: Annotated[List[Any], add_messages]
    chunks: List[Any]
    success_criteria: str
    feedback_on_work: Optional[str]
    success_criteria_met: bool
    user_input_needed: bool


class Result(BaseModel):
    page_content: str
    metadata: Dict[str, Any]


class DocAnalyzerAgent:
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._agent_id = str(uuid.uuid4())

        self._model = model if model else os.getenv("LLM_MODEL", "llama3.2")
        self._provider = provider if provider else os.getenv("LLM_PROVIDER", "ollama")
        self._collection_name = os.getenv("VECTOR_COLLECTION", "documents")
        vector_store_dir = os.getenv("VECTOR_STORE_DIR", ".")
        self._db_name = os.path.join(vector_store_dir, "vector_store.db")

        embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
        self._embeddings = OpenAIEmbeddings(model=embedding_model)

        self._worker_llm_with_tools: Optional[Runnable[Any, Any]] = None
        self._evaluator_llm_with_output: Optional[Runnable[Any, Any]] = None
        self._graph: Optional[Any] = None
        self._vectorstore: Optional[ClientAPI] = None

    async def initialize(self) -> None:
        """
        Initialize the agent and its dependencies.
        """

        self._vectorstore = PersistentClient(path=self._db_name)

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
        :param message: The message to process
        :param success_criteria: The success criteria for the message
        :param history: The history of the conversation
        :param thread: The thread ID
        :return: The response from the agent with the user, reply and feedback.
        """

        config = {"configurable": {"thread_id": thread}}

        history = history[:50]

        state: State = {
            "messages": history + [HumanMessage(content=message)],
            "chunks": [],
            "success_criteria": success_criteria,
            "feedback_on_work": None,
            "success_criteria_met": False,
            "user_input_needed": False,
        }

        assert self._graph is not None, "Agent not initialized; call initialize() first"
        result = await self._graph.ainvoke(state, config=config)

        user = {"role": "user", "content": message}
        reply = {"role": "assistant", "content": result["messages"][-2].content}
        feedback = {"role": "assistant", "content": result["messages"][-1].content}

        return [user, reply, feedback]

    def fetch_chunks(self, question: str) -> List[Any]:
        """
        Fetch the chunks for a question from the vector store.
        :param question: The question to fetch the chunks for
        :return: The chunks found in the vector store
        """

        query: Sequence[float] = self._embeddings.embed_query(str(question))
        assert self._vectorstore is not None, "Agent not initialized; call initialize() first"
        collection = self._vectorstore.get_or_create_collection(self._collection_name)
        results = collection.query(query_embeddings=query, n_results=10)

        chunks = []
        documents = results["documents"] or [[]]
        metadatas = results["metadatas"] or [[]]
        for result in zip(documents[0], metadatas[0]):
            chunks.append(Result(page_content=result[0], metadata=dict(result[1])))

        return chunks

    def _build_graph(self) -> Any:
        graph_builder = StateGraph(State)

        graph_builder.add_edge(START, "document_worker")
        graph_builder.add_node("document_worker", self._document_worker)
        graph_builder.add_node("answer_worker", self._answer_worker)
        graph_builder.add_node("tools", ToolNode(tools=self._tools))
        graph_builder.add_node("evaluator", self._evaluator)

        graph_builder.add_edge("document_worker", "answer_worker")
        graph_builder.add_conditional_edges(
            "answer_worker",
            self._worker_router,
            {"tools": "tools", "evaluator": "evaluator"},
        )
        graph_builder.add_edge("tools", "answer_worker")
        graph_builder.add_conditional_edges(
            "evaluator",
            self._route_based_on_evaluation,
            {"answer_worker": "answer_worker", "END": END},
        )

        memory = MemorySaver()
        graph = graph_builder.compile(checkpointer=memory)

        with open("graph.png", "wb") as f:
            f.write(graph.get_graph().draw_mermaid_png())

        return graph

    def _document_worker(self, state: State) -> Dict[str, Any]:
        logger.info(f"Document worker: {state['messages']}")

        user_message = None
        messages = state["messages"]
        for message in messages:
            if isinstance(message, HumanMessage):
                user_message = message.content
                break

        if user_message is None:
            return {
                "chunks": [],
                "messages": [AIMessage(content="No user message found")],
            }

        chunks = self.fetch_chunks(str(user_message))

        return {
            "chunks": chunks,
            "messages": [AIMessage(content=f"Chunks found: {len(chunks)}")],
        }

    def _answer_worker(self, state: State) -> Dict[str, Any]:
        logger.info(f"Answer worker: {state['messages']}")

        system_message = get_websearch_searcher_prompt(
            self._tools,
            state["chunks"],
            state["success_criteria"],
            state["feedback_on_work"],
        )

        found_system_message = False
        messages = state["messages"]
        for message in messages:
            if isinstance(message, SystemMessage):
                message.content = system_message
                found_system_message = True

        if not found_system_message:
            messages = [SystemMessage(content=system_message)] + messages

        assert self._worker_llm_with_tools is not None, (
            "Agent not initialized; call initialize() first"
        )
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

        system_message = get_websearch_evaluator_background()

        conversation = self._format_conversation(state["messages"])
        user_message = get_websearch_evaluator_prompt(
            conversation,
            state["success_criteria"],
            last_response,
        )

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

        assert self._evaluator_llm_with_output is not None, (
            "Agent not initialized; call initialize() first"
        )
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
            return "answer_worker"
