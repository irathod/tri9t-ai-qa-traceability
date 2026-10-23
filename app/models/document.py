
"""Relational models for document versioning and section storage."""

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    """Represents a logical document, such as the CT-200 manual."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)

    latest_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_versions.id"),
        nullable=True,
    )

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        foreign_keys="DocumentVersion.document_id",
    )


class DocumentVersion(Base):
    """An immutable ingestion of a particular document version."""

    __tablename__ = "document_versions"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_version_number",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"),
        index=True,
    )

    version_number: Mapped[int] = mapped_column(Integer)
    source_file: Mapped[str] = mapped_column(String(255))
    source_hash: Mapped[str] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )

    document: Mapped["Document"] = relationship(
        back_populates="versions",
        foreign_keys=[document_id],
    )

    nodes: Mapped[list["DocumentNode"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
    )


class DocumentNode(Base):
    """A section node belonging to one immutable document version."""

    __tablename__ = "document_nodes"

    __table_args__ = (
        UniqueConstraint(
            "version_id",
            "node_key",
            name="uq_node_key_per_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    version_id: Mapped[int] = mapped_column(
        ForeignKey("document_versions.id"),
        index=True,
    )

    logical_id: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    node_key: Mapped[str] = mapped_column(String(100))

    parent_node_key: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    heading: Mapped[str] = mapped_column(Text)

    section_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    level: Mapped[int] = mapped_column(Integer)

    page_start: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    body_text: Mapped[str] = mapped_column(
        Text,
        default="",
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    version: Mapped["DocumentVersion"] = relationship(
        back_populates="nodes",
    )
