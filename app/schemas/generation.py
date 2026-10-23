
"""Pydantic schemas for LLM-generated QA test cases."""

from pydantic import BaseModel, Field, ConfigDict


class QATestCase(BaseModel):
    """One structured QA test-case idea."""

    title: str = Field(min_length=3, max_length=200)
    objective: str = Field(min_length=5, max_length=1000)
    preconditions: list[str] = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    expected_result: str = Field(min_length=5, max_length=2000)
    priority: str = Field(
        description="One of: Low, Medium, High"
    )


class QATestCaseOutput(BaseModel):
    """Validated LLM response containing QA test cases."""

    test_cases: list[QATestCase] = Field(min_length=3, max_length=5)


class GenerationResponse(BaseModel):
    """Metadata returned when generated test cases are retrieved."""

    model_config = ConfigDict(from_attributes=True)

    generation_id: str
    selection_id: int
    document_id: int
    source_version: int
    node_ids: list[str]
    content_hashes: dict[str, str]
    test_cases: list[QATestCase]
    is_stale: bool = False
    stale_reasons: list[str] = Field(default_factory=list)
