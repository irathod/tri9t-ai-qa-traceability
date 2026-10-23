
"""Ingest parsed document trees and compare document versions."""

import hashlib
import json
import re
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import init_db
from app.models.document import Document, DocumentVersion, DocumentNode


def normalize(text: str) -> str:
    """Normalize whitespace and case for heading matching."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def hash_text(text: str) -> str:
    """Compute a deterministic SHA-256 content hash."""
    normalized = normalize(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def flatten_tree(tree: dict) -> list[dict]:
    """Flatten the parser tree while retaining parent relationships."""
    flattened = []

    def visit(node: dict, parent_key: str | None = None):
        if node["id"] == "root":
            current_key = None
        else:
            current_key = node["id"]

            body = "\n".join(
                item["text"] for item in node.get("content", [])
            )

            flattened.append({
                "node_key": current_key,
                "parent_node_key": parent_key,
                "heading": node.get("heading", ""),
                "section_number": node.get("number"),
                "level": node.get("level", 0),
                "page_start": node.get("page_start"),
                "body_text": body,
                "content_hash": hash_text(
                    node.get("heading", "") + "\n" + body
                ),
            })

        for child in node.get("children", []):
            visit(child, current_key)

    visit(tree)
    return flattened


def load_tree(json_path: Path) -> dict:
    """Read a parser-generated JSON file."""
    if not json_path.is_file():
        raise FileNotFoundError(f"Parsed JSON not found: {json_path}")

    with json_path.open("r", encoding="utf-8") as file:
        return json.load(file)



def match_nodes(
    previous: list[dict],
    current: list[dict],
) -> dict[str, str]:
    """
    Match nodes across document versions.

    Priority:
    1. Exact section number + normalized heading.
    2. Exact normalized heading + parent context.
    3. Unique exact heading match.

    Returns:
        Mapping of current node_key -> previous logical_id.
    """
    from collections import defaultdict

    def norm(value: str | None) -> str:
        return normalize(value or "")

    def parent_heading(
        node: dict,
        nodes: list[dict],
    ) -> str:
        parent_key = node.get("parent_node_key")

        for candidate in nodes:
            if candidate["node_key"] == parent_key:
                return norm(candidate["heading"])

        return ""

    def section_key(node: dict) -> tuple[str, str]:
        return (
            norm(node.get("section_number")),
            norm(node.get("heading")),
        )

    def context_key(
        node: dict,
        nodes: list[dict],
    ) -> tuple[str, str]:
        return (
            norm(node.get("heading")),
            parent_heading(node, nodes),
        )

    previous_by_section = defaultdict(list)
    previous_by_context = defaultdict(list)
    previous_by_heading = defaultdict(list)

    for node in previous:
        previous_by_section[section_key(node)].append(node)
        previous_by_context[context_key(node, previous)].append(node)
        previous_by_heading[norm(node["heading"])].append(node)

    used_old_ids: set[str] = set()
    matches: dict[str, str] = {}

    def assign(node: dict, candidates: list[dict]) -> bool:
        available = [
            old for old in candidates
            if old["logical_id"] not in used_old_ids
        ]

        if len(available) != 1:
            return False

        old = available[0]
        matches[node["node_key"]] = old["logical_id"]
        used_old_ids.add(old["logical_id"])
        return True

    for node in current:
        # First, match using section number and heading.
        if assign(node, previous_by_section[section_key(node)]):
            continue

        # Then match using heading and parent context.
        if assign(node, previous_by_context[context_key(node, current)]):
            continue

        # Finally, use heading only when it is unambiguous.
        assign(node, previous_by_heading[norm(node["heading"])])

    return matches


def ingest_version(
    session: Session,
    json_path: Path,
    document_name: str,
    version_number: int,
) -> DocumentVersion:
    """
    Persist a document version without overwriting prior versions.

    Re-ingesting an existing version is rejected to prevent accidental
    duplicate records or silent replacement of historical content.
    """
    tree = load_tree(json_path)
    nodes = flatten_tree(tree)

    source_hash = tree.get("source_hash") or hash_text(
        json.dumps(tree, sort_keys=True)
    )

    document = session.scalar(
        select(Document).where(Document.name == document_name)
    )

    if document is None:
        document = Document(name=document_name)
        session.add(document)
        session.flush()

    existing = session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.version_number == version_number,
        )
    )

    if existing is not None:
        raise ValueError(
            f"Version {version_number} already exists for {document_name}."
        )

    previous_version = session.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.version_number.desc())
    )

    previous_nodes = []

    if previous_version:
        previous_nodes = [
            {
                "node_key": node.node_key,
                "parent_node_key": node.parent_node_key,
                "heading": node.heading,
                "section_number": node.section_number,
                "level": node.level,
                "page_start": node.page_start,
                "body_text": node.body_text,
                "content_hash": node.content_hash,
                "logical_id": node.logical_id,
            }
            for node in previous_version.nodes
        ]

    # Match only against the immediately preceding version.
    matches = match_nodes(previous_nodes, nodes)

    version = DocumentVersion(
        document_id=document.id,
        version_number=version_number,
        source_file=tree.get("source_file", json_path.name),
        source_hash=source_hash,
    )
    session.add(version)
    session.flush()

    for node in nodes:
        logical_id = matches.get(node["node_key"])

        # Unmatched nodes receive a new logical identity.
        if logical_id is None:
            logical_id = str(uuid.uuid4())

        session.add(DocumentNode(
            version_id=version.id,
            logical_id=logical_id,
            node_key=node["node_key"],
            parent_node_key=node["parent_node_key"],
            heading=node["heading"],
            section_number=node["section_number"],
            level=node["level"],
            page_start=node["page_start"],
            body_text=node["body_text"],
            content_hash=node["content_hash"],
        ))

    document.latest_version_id = version.id
    session.flush()

    return version


def compare_versions(
    previous: DocumentVersion,
    current: DocumentVersion,
) -> list[dict]:
    """
    Compare two versions by logical node identity.

    Results: unchanged, modified, added, or removed.
    """
    old_by_logical = {
        node.logical_id: node for node in previous.nodes
    }
    new_by_logical = {
        node.logical_id: node for node in current.nodes
    }

    results = []

    for logical_id in sorted(set(old_by_logical) | set(new_by_logical)):
        old = old_by_logical.get(logical_id)
        new = new_by_logical.get(logical_id)

        if old is None:
            status = "added"
        elif new is None:
            status = "removed"
        elif old.content_hash == new.content_hash:
            status = "unchanged"
        else:
            status = "modified"

        results.append({
            "logical_id": logical_id,
            "status": status,
            "old_heading": old.heading if old else None,
            "new_heading": new.heading if new else None,
            "old_hash": old.content_hash if old else None,
            "new_hash": new.content_hash if new else None,
        })

    return results
