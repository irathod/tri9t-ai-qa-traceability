
"""SQLite connection and SQLAlchemy base configuration."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
DATABASE_PATH = ROOT_DIR / "tri9t_ai.db"

DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def get_db():
    """Yield a database session for FastAPI or scripts."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables registered with SQLAlchemy."""
    # Import models so SQLAlchemy registers their table metadata.
    from app.models import document, selection  # noqa: F401

    Base.metadata.create_all(bind=engine)
