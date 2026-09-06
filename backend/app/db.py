"""
Database connection and initialization for CaseFill-AI.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from .config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    """Create a new database connection with proper settings."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connections (auto-commit/rollback)."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Column additions applied to existing databases created before these fields existed.
# Fresh databases get them directly from schema.sql.
_CASE_COLUMN_MIGRATIONS = {
    "donor_arranged": "ALTER TABLE cases ADD COLUMN donor_arranged INTEGER NOT NULL DEFAULT 0",
    "aid_transfer_log": "ALTER TABLE cases ADD COLUMN aid_transfer_log TEXT NOT NULL DEFAULT '[]'",
    "child_user_id": "ALTER TABLE cases ADD COLUMN child_user_id TEXT",
    "child_username": "ALTER TABLE cases ADD COLUMN child_username TEXT",
    "child_password": "ALTER TABLE cases ADD COLUMN child_password TEXT",
    "child_login_generated_at": "ALTER TABLE cases ADD COLUMN child_login_generated_at TEXT",
    "submitted_by_fso_id": "ALTER TABLE cases ADD COLUMN submitted_by_fso_id TEXT",
}


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Apply idempotent column migrations (existing databases are never recreated)."""
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(cases)")}
    for col, ddl in _CASE_COLUMN_MIGRATIONS.items():
        if col not in existing_cols:
            conn.execute(ddl)


def init_db():
    """Initialize the database schema and seed data if needed."""
    schema_path = Path(__file__).parent / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with get_db() as conn:
        conn.executescript(schema_sql)
        _migrate_schema(conn)

    # Seed if empty
    cursor = get_connection().execute("SELECT COUNT(*) FROM regions")
    if cursor.fetchone()[0] == 0:
        from .seed import seed_database
        seed_database()


def dict_row(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    if row is None:
        return None
    return dict(row)


def dict_rows(rows: list) -> list:
    """Convert a list of sqlite3.Row to a list of dicts."""
    return [dict(r) for r in rows]
