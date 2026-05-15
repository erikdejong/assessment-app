import json
from pathlib import Path
from pydantic import BaseModel, Field

TEST_FILE = str(Path(__file__).parent / "tests.jsonl")


class TestQuestion(BaseModel):
    """
    A test question with expected keywords and reference answer.
    """

    question: str = Field(description="The question from the user")
    keywords: list[str] = Field(description="The keywords that must appear in the context")
    answer: str = Field(description="The answer for this question")
    category: str = Field(description="The category of the question")


def load_tests() -> list[TestQuestion]:
    """
    Load test questions from JSONL file.
    """
    tests = []
    with open(TEST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line.strip())
            tests.append(TestQuestion(**data))
    return tests
