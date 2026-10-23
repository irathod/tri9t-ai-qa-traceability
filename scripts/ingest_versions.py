
"""Rebuild the development database and compare CT-200 manual versions."""

import sys
from pathlib import Path

# Make the project root importable when running this script directly.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.database import DATABASE_PATH, SessionLocal, init_db
from app.models.document import DocumentVersion
from app.services.versioning import ingest_version, compare_versions


DATA = ROOT / "data"


def reset_development_database() -> None:
    """
    Delete the local development database for a clean rebuild.

    WARNING: This permanently deletes all data in this SQLite file.
    Use only for development, not production.
    """
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
        print("Removed existing development database.")


def main() -> None:
    # Step 1: Start with a clean development database.
    reset_development_database()

    # Step 2: Create the database tables.
    init_db()
    print("Database initialized.")

    # Step 3: Ingest both document versions.
    with SessionLocal() as session:
        try:
            v1 = ingest_version(
                session=session,
                json_path=DATA / "ct200_manual_parsed.json",
                document_name="CT-200",
                version_number=1,
            )
            session.commit()
            v1_id = v1.id
            print(f"Ingested v1: database version ID {v1_id}")

            v2 = ingest_version(
                session=session,
                json_path=DATA / "ct200_manual_v2_parsed.json",
                document_name="CT-200",
                version_number=2,
            )
            session.commit()
            v2_id = v2.id
            print(f"Ingested v2: database version ID {v2_id}")

            # Step 4: Reload both versions for comparison.
            v1 = session.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.id == v1_id
                )
            )
            v2 = session.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.id == v2_id
                )
            )

            if v1 is None or v2 is None:
                raise RuntimeError(
                    "Could not reload both document versions."
                )

            # Step 5: Compare logical nodes across versions.
            results = compare_versions(v1, v2)

            print("\nVersion comparison:")
            for item in results:
                if item["status"] != "unchanged":
                    heading = (
                        item["new_heading"]
                        or item["old_heading"]
                        or item["logical_id"]
                    )
                    print(f'{item["status"].upper():8} {heading}')

            print(f"\nCompared {len(results)} logical nodes.")

        except Exception:
            session.rollback()
            raise


if __name__ == "__main__":
    main()
