"""Database initialization and session management."""

from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from src.config.settings import settings

# Ensure data directory exists
Path(settings.data_dir).mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.db_url, echo=False)


def init_db() -> None:
    """Create all tables."""
    # Import models so SQLModel registers them
    import src.data.models  # noqa: F401
    import src.data.models_signal  # noqa: F401
    import src.data.models_journal  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
