
"""Pydantic schemas for version-pinned selections."""

from pydantic import BaseModel, Field, ConfigDict


class SelectionCreate(BaseModel):
    """Request body for creating a section selection."""

    name: str = Field(min_length=1, max_length=255)
    document_id: int = Field(gt=0)
    version_number: int = Field(ge=1)
    logical_ids: list[str] = Field(min_length=1)


class SelectionResponse(BaseModel):
    """Response containing a saved selection."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    document_id: int
    version_number: int
    logical_ids: list[str]
