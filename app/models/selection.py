
"""Version-pinned section selections."""

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SectionSelection(Base):
    """A saved selection of sections from exact document versions."""

    __tablename__ = "section_selections"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"),
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer)
    logical_ids: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
