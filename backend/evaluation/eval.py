import asyncio
import math
import os
import sys
import uuid
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import Any, AsyncIterator, Iterator, cast

from evaluation.test import TestQuestion, load_tests
from agents.doc_analyzer_agent import DocAnalyzerAgent, Result

load_dotenv(override=True)

EVALUATION_MODEL = "gpt-5-mini"
DB_NAME = os.getenv("VECTOR_STORE_DIR") if os.getenv("VECTOR_STORE_DIR") else "vector_store"

llm = ChatOpenAI(temperature=0.1, model=EVALUATION_MODEL)

doc_analyzer_agent = DocAnalyzerAgent()


class RetrievalEval(BaseModel):
    """
    Evaluation metrics for retrieval performance.
    """

    mrr: float = Field(description="Mean Reciprocal Rank - average across all keywords")
    ndcg: float = Field(description="Normalized Discounted Cumulative Gain (binary relevance)")
    keywords_found: int = Field(description="Number of keywords found in top-k results")
    total_keywords: int = Field(description="Total number of keywords to find")
    keyword_coverage: float = Field(description="Percentage of keywords found")


class AnswerEval(BaseModel):
    """
    LLM-as-a-judge evaluation of answer quality.
    """

    feedback: str = Field(
        description=(
            "Concise feedback on the answer quality, comparing it to the reference "
            "answer and evaluating based on the retrieved context"
        )
    )
    accuracy: float = Field(
        description=(
            "How factually correct is the answer compared to the reference answer? "
            "1 (wrong. any wrong answer must score 1) to 5 (ideal - perfectly accurate). "
            "An acceptable answer would score 3."
        )
    )
    completeness: float = Field(
        description=(
            "How complete is the answer in addressing all aspects of the question? "
            "1 (very poor - missing key information) to 5 (ideal - all the information "
            "from the reference answer is provided completely). Only answer 5 if ALL "
            "information from the reference answer is included."
        )
    )
    relevance: float = Field(
        description=(
            "How relevant is the answer to the specific question asked? "
            "1 (very poor - off-topic) to 5 (ideal - directly addresses question and "
            "gives no additional information). Only answer 5 if the answer is completely "
            "relevant to the question and gives no additional information."
        )
    )


def calculate_mrr(keyword: str, retrieved_docs: list[Any]) -> float:
    """
    Calculate reciprocal rank for a single keyword (case-insensitive).
    """
    keyword_lower = keyword.lower()
    for rank, doc in enumerate(retrieved_docs, start=1):
        if keyword_lower in doc.page_content.lower():
            return 1.0 / rank
    return 0.0


def calculate_dcg(relevances: list[int], k: int) -> float:
    """
    Calculate Discounted Cumulative Gain.
    """
    dcg = 0.0
    for i in range(min(k, len(relevances))):
        dcg += relevances[i] / math.log2(i + 2)  # i+2 because rank starts at 1
    return dcg


def calculate_ndcg(keyword: str, retrieved_docs: list[Any], k: int = 10) -> float:
    """
    Calculate nDCG for a single keyword (binary relevance, case-insensitive).
    """
    keyword_lower = keyword.lower()

    # Binary relevance: 1 if keyword found, 0 otherwise
    relevances = [
        1 if keyword_lower in doc.page_content.lower() else 0 for doc in retrieved_docs[:k]
    ]

    # DCG
    dcg = calculate_dcg(relevances, k)

    # Ideal DCG (best case: keyword in first position)
    ideal_relevances = sorted(relevances, reverse=True)
    idcg = calculate_dcg(ideal_relevances, k)

    return dcg / idcg if idcg > 0 else 0.0


def evaluate_retrieval(test: TestQuestion, k: int = 10) -> RetrievalEval:
    """
    Evaluate retrieval performance for a test question.
    :param test: TestQuestion object containing question and keywords
    :param k: Number of top documents to retrieve (default 10)
    :return: RetrievalEval object with MRR, nDCG, and keyword coverage metrics
    """
    retrieved_docs: list[Result] = doc_analyzer_agent.fetch_chunks(test.question)

    # Calculate MRR (average across all keywords)
    mrr_scores = [calculate_mrr(keyword, retrieved_docs) for keyword in test.keywords]
    avg_mrr = sum(mrr_scores) / len(mrr_scores) if mrr_scores else 0.0

    # Calculate nDCG (average across all keywords)
    ndcg_scores = [calculate_ndcg(keyword, retrieved_docs, k) for keyword in test.keywords]
    avg_ndcg = sum(ndcg_scores) / len(ndcg_scores) if ndcg_scores else 0.0

    # Calculate keyword coverage
    keywords_found = sum(1 for score in mrr_scores if score > 0)
    total_keywords = len(test.keywords)
    keyword_coverage = (keywords_found / total_keywords * 100) if total_keywords > 0 else 0.0

    return RetrievalEval(
        mrr=avg_mrr,
        ndcg=avg_ndcg,
        keywords_found=keywords_found,
        total_keywords=total_keywords,
        keyword_coverage=keyword_coverage,
    )


async def evaluate_answer(test: TestQuestion, session_id: str) -> tuple[AnswerEval, str]:
    """
    Evaluate answer quality using LLM-as-a-judge (async).
    :param test: TestQuestion object containing question and reference answer
    :param session_id: The session ID for the conversation
    :return: Tuple of (AnswerEval object, generated_answer string)
    """

    success_criteria = """
The assistant should be able give a valid answer to the user's question.
The answer should be based on the information from the documents.
If the questions contains a year, the answer should be based on the information
from the documents from that year.
The answer should be in the language of the user's question.
"""

    # Get RAG response using doc_analyzer_agent
    response_messages = await doc_analyzer_agent.process_message(
        test.question, success_criteria, [], session_id
    )
    # `process_message` returns a list of {role, content} dicts; pull the
    # assistant reply for use as the generated answer string.
    generated_answer = str(response_messages[1]["content"]) if len(response_messages) > 1 else ""

    judge_system_prompt = (
        "You are an expert evaluator assessing the quality of answers. "
        "Evaluate the generated answer by comparing it to the reference answer. "
        "Only give 5/5 scores for perfect answers."
    )

    judge_user_prompt = f"""Question:
{test.question}

Generated Answer:
{generated_answer}

Reference Answer:
{test.answer}

Please evaluate the generated answer on three dimensions:
1. Accuracy: How factually correct is it compared to the reference answer?
   Only give 5/5 scores for perfect answers.
2. Completeness: How thoroughly does it address all aspects of the question,
   covering all the information from the reference answer?
3. Relevance: How well does it directly answer the specific question asked,
   giving no additional information?

Provide detailed feedback and scores from 1 (very poor) to 5 (ideal) for each
dimension. If the answer is wrong, then the accuracy score must be 1."""

    judge_messages = [
        {"role": "system", "content": judge_system_prompt},
        {"role": "user", "content": judge_user_prompt},
    ]

    # Call LLM judge with structured outputs (async)
    judge_response = await llm.ainvoke(judge_messages, response_format=AnswerEval)
    answer_eval = AnswerEval.model_validate_json(cast(str, judge_response.content))

    return answer_eval, generated_answer


def evaluate_all_retrieval() -> Iterator[tuple[TestQuestion, RetrievalEval, float]]:
    """
    Evaluate all retrieval tests.
    """

    asyncio.run(doc_analyzer_agent.initialize())

    tests = load_tests()
    total_tests = len(tests)
    print(f"Evaluating retrieval for {total_tests:,} tests")

    for index, test in enumerate(tests):
        result = evaluate_retrieval(test)
        progress = (index + 1) / total_tests
        yield test, result, progress


async def evaluate_all_answers() -> AsyncIterator[tuple[TestQuestion, AnswerEval, float]]:
    """
    Evaluate all answers to tests using batched async execution.
    """

    await doc_analyzer_agent.initialize()
    session_id = str(uuid.uuid4())

    tests = load_tests()
    total_tests = len(tests)
    print(f"Evaluating answers for {total_tests:,} tests")

    for index, test in enumerate(tests):
        result = (await evaluate_answer(test, session_id))[0]
        progress = (index + 1) / total_tests
        yield test, result, progress


async def run_cli_evaluation(test_number: int) -> None:
    """Run evaluation for a specific test (async helper for CLI)."""
    # Load tests
    tests = load_tests()

    if test_number < 0 or test_number >= len(tests):
        print(f"Error: test_row_number must be between 0 and {len(tests) - 1}")
        sys.exit(1)

    # Get the test
    test = tests[test_number]

    # Print test info
    print(f"\n{'=' * 80}")
    print(f"Test #{test_number}")
    print(f"{'=' * 80}")
    print(f"Question: {test.question}")
    print(f"Keywords: {test.keywords}")
    print(f"Category: {test.category}")
    print(f"Reference Answer: {test.answer}")

    # Retrieval Evaluation
    print(f"\n{'=' * 80}")
    print("Retrieval Evaluation")
    print(f"{'=' * 80}")

    retrieval_result = evaluate_retrieval(test)

    print(f"MRR: {retrieval_result.mrr:.4f}")
    print(f"nDCG: {retrieval_result.ndcg:.4f}")
    print(
        f"Keywords Found: {retrieval_result.keywords_found}/{retrieval_result.total_keywords}"
    )
    print(f"Keyword Coverage: {retrieval_result.keyword_coverage:.1f}%")

    # Answer Evaluation
    print(f"\n{'=' * 80}")
    print("Answer Evaluation")
    print(f"{'=' * 80}")

    # TODO: Source the answering context from a web search / summary agent
    # once they are available in this codebase.
    summarize_context = ""
    answer_result, generated_answer = await evaluate_answer(test, summarize_context)

    print(f"\nGenerated Answer:\n{generated_answer}")
    print(f"\nFeedback:\n{answer_result.feedback}")
    print("\nScores:")
    print(f"  Accuracy: {answer_result.accuracy:.2f}/5")
    print(f"  Completeness: {answer_result.completeness:.2f}/5")
    print(f"  Relevance: {answer_result.relevance:.2f}/5")
    print(f"\n{'=' * 80}\n")


def main() -> None:
    """CLI to evaluate a specific test by row number."""
    if len(sys.argv) != 2:
        print("Usage: uv run eval.py <test_row_number>")
        sys.exit(1)

    try:
        test_number = int(sys.argv[1])
    except ValueError:
        print("Error: test_row_number must be an integer")
        sys.exit(1)

    asyncio.run(run_cli_evaluation(test_number))


if __name__ == "__main__":
    main()
