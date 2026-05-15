import asyncio
import math
import sys
from typing import Any, AsyncIterator, Iterator
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from evaluation.test import TestQuestion, load_tests
from agents.doc_analyzer_agent import DocAnalyzerAgent

load_dotenv(override=True)

doc_analyzer_agent = DocAnalyzerAgent()

EVALUATION_MODEL = "gpt-5-mini"
db_name = "vector_db"


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
    """Calculate reciprocal rank for a single keyword (case-insensitive)."""
    keyword_lower = keyword.lower()
    for rank, doc in enumerate(retrieved_docs, start=1):
        if keyword_lower in doc.page_content.lower():
            return 1.0 / rank
    return 0.0


def calculate_dcg(relevances: list[int], k: int) -> float:
    """Calculate Discounted Cumulative Gain."""
    dcg = 0.0
    for i in range(min(k, len(relevances))):
        dcg += relevances[i] / math.log2(i + 2)  # i+2 because rank starts at 1
    return dcg


def calculate_ndcg(keyword: str, retrieved_docs: list[Any], k: int = 10) -> float:
    """Calculate nDCG for a single keyword (binary relevance, case-insensitive)."""
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

    Args:
        test: TestQuestion object containing question and keywords
        k: Number of top documents to retrieve (default 10)

    Returns:
        RetrievalEval object with MRR, nDCG, and keyword coverage metrics
    """
    # TODO: Implement retrieval against the vector store.
    retrieved_docs: list[Any] = []

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


async def evaluate_answer(test: TestQuestion, context: str) -> tuple[AnswerEval, str]:
    """
    Evaluate answer quality using LLM-as-a-judge (async).

    Args:
        test: TestQuestion object containing question and reference answer
        context: Background context used by the answering agent

    Returns:
        Tuple of (AnswerEval object, generated_answer string)
    """
    # TODO: Wire up the answering agent and LLM judge once those components are
    # available in this codebase. The previous implementation referenced
    # `task_description_agent` and `llm_provider`, which do not exist here yet.
    raise NotImplementedError(
        "evaluate_answer is not implemented: missing task description agent "
        "and LLM judge provider."
    )


def evaluate_all_retrieval() -> Iterator[tuple[TestQuestion, RetrievalEval, float]]:
    """Evaluate all retrieval tests."""
    tests = load_tests()
    total_tests = len(tests)
    for index, test in enumerate(tests):
        result = evaluate_retrieval(test)
        progress = (index + 1) / total_tests
        yield test, result, progress


async def evaluate_all_answers() -> AsyncIterator[tuple[TestQuestion, AnswerEval, float]]:
    """
    Evaluate all answers to tests using batched async execution.
    """

    print("Loading tests")
    tests = load_tests()
    total_tests = len(tests)

    print(f"Evaluating answers for {total_tests:,} tests")
    for index, test in enumerate(tests):
        print(f"Evaluating test {index+1}/{total_tests}")
        # TODO: Provide real context once `web_search_service` and the
        # `task_description_agent` summary helper are available.
        context = ""
        result = (await evaluate_answer(test, context))[0]
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
    print(f"MBA data: {test.mba_data}")
    print(f"Keywords: {test.keywords}")
    print(f"Category: {test.category}")
    print(f"Reference Answer: {test.reference_answer}")
    print(f"Reference Justification: {test.reference_justification}")

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
