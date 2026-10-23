
"""Inspect the actual content changes stored in SQLite."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.database import SessionLocal
from app.models.document import DocumentVersion
from app.services.versioning import compare_versions


def preview(text: str | None, limit: int = 700) -> str:
    """Keep terminal output readable."""
    if not text:
        return "(empty)"
    return text[:limit] + ("..." if len(text) > limit else "")


def main() -> None:
    with SessionLocal() as session:
        versions = session.scalars(
            select(DocumentVersion)
            .order_by(DocumentVersion.version_number)
        ).all()

        if len(versions) < 2:
            print("Please ingest both manual versions first.")
            return

        v1 = next(v for v in versions if v.version_number == 1)
        v2 = next(v for v in versions if v.version_number == 2)

        changes = compare_versions(v1, v2)

        old_nodes = {node.logical_id: node for node in v1.nodes}
        new_nodes = {node.logical_id: node for node in v2.nodes}

        for change in changes:
            if change["status"] == "unchanged":
                continue

            logical_id = change["logical_id"]
            old = old_nodes.get(logical_id)
            new = new_nodes.get(logical_id)

            print("\n" + "=" * 72)
            print("Status:", change["status"].upper())
            print("Old heading:", old.heading if old else "(none)")
            print("New heading:", new.heading if new else "(none)")

            print("\n--- V1 content ---")
            print(preview(old.body_text if old else None))

            print("\n--- V2 content ---")
            print(preview(new.body_text if new else None))


if __name__ == "__main__":
    main()
