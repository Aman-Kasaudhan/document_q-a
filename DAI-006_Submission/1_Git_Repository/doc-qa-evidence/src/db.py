"""SQLite connection and schema initialisation."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


def connect(db_path: Path | str) -> sqlite3.Connection:
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables if missing. Safe to call on every start."""
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    except sqlite3.OperationalError as exc:
        if "fts5" in str(exc).lower():
            raise RuntimeError(
                "This Python's SQLite build lacks FTS5. Use a Python build with FTS5 enabled."
            ) from exc
        raise
    conn.commit()
