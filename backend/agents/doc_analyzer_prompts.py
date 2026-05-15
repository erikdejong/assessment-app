from typing import List, Any
from pydantic import BaseModel, Field


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


def get_websearch_searcher_prompt(
    tools: List[Any],
    data: List[Any],
    success_criteria: str,
    feedback_on_work: str | None = None,
) -> str:
    message = f"""
You are a helpful assistant that can use tools to complete tasks.
To evaluate the information, you can use the following tools:
{tools}

The data from the documents:
{data}

Use the tools only to validate the information from the documents in order to
answer the user's question.

You keep working on a task until either you have a question or answer for the user,
or the success criteria is met.

This is the success criteria:
{success_criteria}

You should reply either with a question for the user about this assignment,
or with your final response.
If you have a question for the user, you need to reply by clearly stating your question.
An example might be:

Question: please clarify whether you want a summary or a detailed answer

If you've finished, reply with the final answer, and don't ask a question;
simply reply with the answer.
"""

    if feedback_on_work:
        message += f"""
Previously you thought you completed the assignment, but your reply was rejected
because the success criteria was not met.

Here is the feedback on why this was rejected:
{feedback_on_work}

With this feedback, please continue the assignment, ensuring that you meet the
success criteria or have a question for the user.
"""

    return message


def get_websearch_evaluator_background() -> str:
    return """
You are an evaluator that determines if a task has been completed successfully by an Assistant.
Assess the Assistant's last response based on the given criteria. Respond with your feedback,
and with your decision on whether the success criteria has been met,
and whether more input is needed from the user.
"""


def get_websearch_evaluator_prompt(
    conversation: str,
    success_criteria: str,
    last_response: str,
) -> str:
    return f"""
You are evaluating a conversation between the User and Assistant.
You decide what action to take based on the last response from the Assistant.

The entire conversation with the assistant, with the user's original request and all replies,
is:
{conversation}

The success criteria for this assignment is:
{success_criteria}

And the final response from the Assistant that you are evaluating is:
{last_response}

Respond with your feedback, and decide if the success criteria is met by this response.
Also, decide if more user input is required, either because the assistant has a question,
needs clarification, or seems to be stuck and unable to answer without help.
"""
