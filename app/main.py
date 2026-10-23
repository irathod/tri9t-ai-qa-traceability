
"""FastAPI application for CT-200 document traceability."""
from fastapi import HTTPException
from app.services.generation_service import generate_test_cases

from app.models.document import DocumentNode
from app.models.selection import SectionSelection
from app.schemas.selection import SelectionCreate


from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.models.document import Document, DocumentVersion
from app.services.versioning import compare_versions

app = FastAPI(
    title="Tri9T AI Document Traceability API",
    description=(
        "API for browsing manual versions, retrieving sections, "
        "comparing document versions, and detecting stale content."
    ),
    version="0.2.0",
)


@app.on_event("startup")
def startup() -> None:
    """Create database tables if they do not already exist."""
    init_db()


def get_document_or_404(
    db: Session, document_id: int
) -> Document:
    """Return a document or raise a clear 404 response."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def get_version_or_404(
    db: Session, document_id: int, version_number: int
) -> DocumentVersion:
    """Find a specific version belonging to a document."""
    version = db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.version_number == version_number,
        )
    )
    if version is None:
        raise HTTPException(
            status_code=404,
            detail=f"Version {version_number} not found for this document",
        )
    return version


@app.get("/")
def home():
    return {
        "message": "Tri9T AI Document Traceability API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    """List logical documents stored in the database."""
    documents = db.scalars(
        select(Document).order_by(Document.name)
    ).all()

    return [
        {
            "id": doc.id,
            "name": doc.name,
            "latest_version_id": doc.latest_version_id,
        }
        for doc in documents
    ]


@app.get("/documents/{document_id}/versions")
def list_versions(
    document_id: int,
    db: Session = Depends(get_db),
):
    """List all ingested versions of a document."""
    get_document_or_404(db, document_id)

    versions = db.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number)
    ).all()

    return [
        {
            "id": version.id,
            "version_number": version.version_number,
            "source_file": version.source_file,
            "source_hash": version.source_hash,
        }
        for version in versions
    ]



@app.get(
    "/documents/{document_id}/compare",
    responses={
        400: {"description": "Cannot compare the same version"},
        404: {"description": "Document or version not found"},
    },
)

def compare_document_versions(
    document_id: int,
    from_version: int = Query(default=1, ge=1),
    to_version: int = Query(default=2, ge=1),
    db: Session = Depends(get_db),
):
    """Compare two stored versions of the same document."""
    document = get_document_or_404(db, document_id)

    if from_version == to_version:
        raise HTTPException(
            status_code=400,
            detail="Choose two different version numbers",
        )

    old = get_version_or_404(db, document_id, from_version)
    new = get_version_or_404(db, document_id, to_version)

    # compare_versions expects chronological previous/current order.
    if old.version_number > new.version_number:
        old, new = new, old

    changes = compare_versions(old, new)

    summary = {
        status: sum(1 for item in changes if item["status"] == status)
        for status in ("unchanged", "modified", "added", "removed")
    }

    return {
        "document": document.name,
        "from_version": from_version,
        "to_version": to_version,
        "total_nodes_compared": len(changes),
        "summary": summary,
        "changes": changes,
    }


@app.get("/documents/{document_id}/versions/{version_number}/sections")
def retrieve_sections(
    document_id: int,
    version_number: int,
    section_number: str | None = Query(default=None),
    q: str | None = Query(
        default=None,
        description="Search section headings and body text",
        min_length=1,
        max_length=200,
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve sections from one exact document version.

    Filters can be combined. For example, section_number=4.3
    selects that numbered section, while q=alarm searches content.
    """
    get_document_or_404(db, document_id)
    version = get_version_or_404(db, document_id, version_number)

    nodes = version.nodes

    if section_number is not None:
        target = section_number.strip().casefold()
        nodes = [
            node for node in nodes
            if (node.section_number or "").strip().casefold() == target
        ]

    if q is not None:
        search_text = q.strip().casefold()
        nodes = [
            node for node in nodes
            if search_text in (node.heading or "").casefold()
            or search_text in (node.body_text or "").casefold()
        ]

    nodes = sorted(
        nodes,
        key=lambda node: (
            node.page_start if node.page_start is not None else 0,
            node.section_number or "",
            node.heading or "",
        ),
    )

    return {
        "document_id": document_id,
        "version_number": version.version_number,
        "source_file": version.source_file,
        "count": len(nodes),
        "sections": [
            {
                "logical_id": node.logical_id,
                "section_number": node.section_number,
                "heading": node.heading,
                "level": node.level,
                "page_start": node.page_start,
                "body_text": node.body_text,
                "content_hash": node.content_hash,
            }
            for node in nodes
        ],
    }


@app.get("/documents/{document_id}/staleness")
def detect_staleness(
    document_id: int,
    baseline_version: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
):
    """
    Identify baseline sections changed or removed in the latest version.

    This is a traceability signal for human review, not a clinical
    safety determination.
    """
    document = get_document_or_404(db, document_id)

    baseline = get_version_or_404(
        db, document_id, baseline_version
    )

    latest = db.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
    )

    if latest is None:
        raise HTTPException(
            status_code=404,
            detail="No document versions are available",
        )

    if baseline.id == latest.id:
        raise HTTPException(
            status_code=400,
            detail=(
                "The baseline is already the latest version; "
                "choose an older baseline version."
            ),
        )

    changes = compare_versions(baseline, latest)

    # Existing baseline content that changed or disappeared
    # should be reviewed for possible staleness.
    affected = [
        item for item in changes
        if item["status"] in ("modified", "removed")
    ]

    added = [
        item for item in changes if item["status"] == "added"
    ]

    return {
        "document": document.name,
        "baseline_version": baseline.version_number,
        "latest_version": latest.version_number,
        "potentially_stale_count": len(affected),
        "new_section_count": len(added),
        "requires_review": bool(affected),
        "note": (
            "Potential staleness is based on version changes. "
            "Review the source manuals before making clinical "
            "or regulatory decisions."
        ),
        "potentially_stale_sections": affected,
        "new_sections": added,
    }

@app.post("/selections", status_code=201)
def create_selection(
    payload: SelectionCreate,
    db: Session = Depends(get_db),
):
    """Save selected nodes against one exact document version."""

    get_document_or_404(db, payload.document_id)

    version = get_version_or_404(
        db,
        payload.document_id,
        payload.version_number,
    )

    # Reject duplicate IDs to avoid ambiguous selections.
    if len(payload.logical_ids) != len(set(payload.logical_ids)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate logical IDs are not allowed",
        )

    # Every selected node must exist in the requested version.
    available_ids = {
        node.logical_id for node in version.nodes
    }

    missing_ids = [
        logical_id
        for logical_id in payload.logical_ids
        if logical_id not in available_ids
    ]

    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Some selected nodes do not exist "
                           "in this document version",
                "missing_logical_ids": missing_ids,
            },
        )

    selection = SectionSelection(
        name=payload.name.strip(),
        document_id=payload.document_id,
        version_number=payload.version_number,
        logical_ids=payload.logical_ids,
    )

    if not selection.name:
        raise HTTPException(
            status_code=422,
            detail="Selection name cannot be empty",
        )

    try:
        db.add(selection)
        db.commit()
        db.refresh(selection)
    except Exception:
        db.rollback()
        raise

    return {
        "id": selection.id,
        "name": selection.name,
        "document_id": selection.document_id,
        "version_number": selection.version_number,
        "logical_ids": selection.logical_ids,
        "message": "Selection created successfully",
    }


@app.get("/selections/{selection_id}")
def get_selection(
    selection_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve a selection and its exact saved section content."""

    selection = db.get(SectionSelection, selection_id)

    if selection is None:
        raise HTTPException(
            status_code=404,
            detail="Selection not found",
        )

    version = get_version_or_404(
        db,
        selection.document_id,
        selection.version_number,
    )

    selected_ids = set(selection.logical_ids)

    sections = [
        {
            "logical_id": node.logical_id,
            "section_number": node.section_number,
            "heading": node.heading,
            "level": node.level,
            "body_text": node.body_text,
            "content_hash": node.content_hash,
        }
        for node in version.nodes
        if node.logical_id in selected_ids
    ]

    # Detect unexpected missing nodes rather than silently omitting them.
    found_ids = {section["logical_id"] for section in sections}
    missing_ids = [
        logical_id
        for logical_id in selection.logical_ids
        if logical_id not in found_ids
    ]

    if missing_ids:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Saved selection references missing nodes",
                "missing_logical_ids": missing_ids,
            },
        )

    # Preserve the original order requested by the user.
    sections_by_id = {
        section["logical_id"]: section
        for section in sections
    }

    ordered_sections = [
        sections_by_id[logical_id]
        for logical_id in selection.logical_ids
    ]

    return {
        "id": selection.id,
        "name": selection.name,
        "document_id": selection.document_id,
        "version_number": selection.version_number,
        "created_at": selection.created_at,
        "sections": ordered_sections,
        "count": len(ordered_sections),
    }

@app.post("/selections/{selection_id}/generate", status_code=201)
def generate_for_selection(
    selection_id: int,
    db: Session = Depends(get_db),
):
    """Generate QA test cases from a version-pinned selection."""

    selection = (
        db.query(SectionSelection)
        .filter(SectionSelection.id == selection_id)
        .first()
    )

    if selection is None:
        raise HTTPException(
            status_code=404,
            detail=f"Selection {selection_id} not found.",
        )

    version = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == selection.document_id,
            DocumentVersion.version_number == selection.version_number,
        )
        .first()
    )

    if version is None:
        raise HTTPException(
            status_code=404,
            detail="The selection's document version was not found.",
        )

    nodes = (
        db.query(DocumentNode)
        .filter(DocumentNode.version_id == version.id)
        .all()
    )

    nodes_by_logical_id = {node.logical_id: node for node in nodes}

    sections = []

    for logical_id in selection.logical_ids:
        node = nodes_by_logical_id.get(logical_id)

        if node is None:
            raise HTTPException(
                status_code=409,
                detail=f"Selected section {logical_id} no longer exists.",
            )

        sections.append(
            {
                "logical_id": node.logical_id,
                "heading": node.heading or "Untitled section",
                "body_text": node.body_text or "",
                "content_hash": node.content_hash,
            }
        )

    try:
        record = generate_test_cases(
            selection_id=selection.id,
            document_id=selection.document_id,
            source_version=selection.version_number,
            sections=sections,
        )
        return record

    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


