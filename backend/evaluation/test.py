import json
from pathlib import Path
from pydantic import BaseModel, Field

TEST_FILE = str(Path(__file__).parent / "tests.jsonl")


class TestQuestion(BaseModel):
    """A test question with expected keywords and reference answer."""

    mba_data: dict[str, str] = Field(description="De gegevens van de MBA")
    keywords: list[str] = Field(description="De keywords die in de context moeten voorkomen")
    reference_answer: str = Field(description="De referentie antwoord voor deze vraag")
    reference_justification: str = Field(description="De referentie justificatie voor deze vraag")
    category: str = Field(description="De categorie van de vraag")


def load_tests() -> list[TestQuestion]:
    """Load test questions from JSONL file."""
    tests = []
    with open(TEST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line.strip())
            tests.append(TestQuestion(**data))
    return tests
