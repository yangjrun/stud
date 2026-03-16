"""Database initialization and session management."""

import sqlite3
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from src.config.settings import settings

# Ensure data directory exists
Path(settings.data_dir).mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.db_url, echo=False)


def _migrate_add_columns(db_path: str) -> None:
    """Add new columns to existing tables (SQLite ALTER TABLE)."""
    migrations: list[tuple[str, str, str]] = [
        # (table, column, type_default)
        ("forecast_candidate", "tier", "VARCHAR(2) DEFAULT NULL"),
        ("forecast_backtest_run", "avg_tier_a_hit_rate", "FLOAT DEFAULT NULL"),
        ("forecast_backtest_run", "avg_tier_b_hit_rate", "FLOAT DEFAULT NULL"),
        ("forecast_backtest_run", "avg_tier_c_hit_rate", "FLOAT DEFAULT NULL"),
        ("forecast_backtest_day", "tier_a_count", "INTEGER DEFAULT 0"),
        ("forecast_backtest_day", "tier_a_hits", "INTEGER DEFAULT 0"),
        ("forecast_backtest_day", "tier_b_count", "INTEGER DEFAULT 0"),
        ("forecast_backtest_day", "tier_b_hits", "INTEGER DEFAULT 0"),
        ("forecast_backtest_day", "tier_c_count", "INTEGER DEFAULT 0"),
        ("forecast_backtest_day", "tier_c_hits", "INTEGER DEFAULT 0"),
    ]

    conn = sqlite3.connect(db_path)
    try:
        for table, column, col_type in migrations:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create all tables."""
    # Import models so SQLModel registers them
    import src.data.models  # noqa: F401
    import src.data.models_signal  # noqa: F401
    import src.data.models_journal  # noqa: F401
    import src.data.models_backtest  # noqa: F401

    SQLModel.metadata.create_all(engine)

    # Apply column migrations for existing tables
    db_path = settings.db_url.replace("sqlite:///", "")
    if Path(db_path).exists():
        _migrate_add_columns(db_path)


def get_session() -> Session:
    return Session(engine)
