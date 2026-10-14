"""Ingestion pipeline: scan -> validate -> normalise -> hash -> chunk -> store.

Idempotent: re-running with unchanged files changes nothing; a changed file replaces its
old chunks; invalid files are rejected and logged instead of crashing the run.
"""
from __future__ import annotations

import hashlib
import sqlite3
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .chunking import chunk_text, normalise

SUPPORTED_EXTENSIONS = {".txt", ".md"}


@dataclass
class IngestSummary:
    run_id: str
    ingested: int = 0
    updated: int = 0
    skipped_unchanged: int = 0
    rejected: int = 0
    failed: int = 0
    details: list[tuple[str, str, str]] = field(default_factory=list)  # (file, status, reason)

    def record(self, filename: str, status: str, reason: str = "") -> None:
        setattr(self, status, getattr(self, status) + 1)
        self.details.append((filename, status, reason))


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_and_validate(path: Path) -> tuple[Optional[str], Optional[str]]:
    """Return (normalised_text, None) or (None, rejection_reason)."""
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return None, f"unsupported_extension:{path.suffix or 'none'}"
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, f"unreadable:{exc.__class__.__name__}"
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, "invalid_encoding:not_utf8"
    text = normalise(text)
    if not text:
        return None, "empty_file"
    return text, None


def _delete_document(conn: sqlite3.Connection, doc_id: int) -> None:
    conn.execute(
        "DELETE FROM chunks_fts WHERE chunk_id IN (SELECT chunk_id FROM chunks WHERE doc_id = ?)",
        (doc_id,),
    )
    conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))  # chunks cascade


def _store_document(conn, filename, text, content_hash, size, overlap) -> int:
    cur = conn.execute(
        "INSERT INTO documents (filename, content_hash, char_count) VALUES (?, ?, ?)",
        (filename, content_hash, len(text)),
    )
    doc_id = cur.lastrowid
    chunks = chunk_text(text, size, overlap)
    for ch in chunks:
        c = conn.execute(
            "INSERT INTO chunks (doc_id, chunk_index, text, char_start, char_end, chunk_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (doc_id, ch.index, ch.text, ch.start, ch.end, sha256(ch.text)),
        )
        conn.execute("INSERT INTO chunks_fts (text, chunk_id) VALUES (?, ?)", (ch.text, c.lastrowid))
    return len(chunks)


def _log(conn, run_id, filename, status, reason="") -> None:
    conn.execute(
        "INSERT INTO ingestion_log (run_id, filename, status, reason) VALUES (?, ?, ?, ?)",
        (run_id, filename, status, reason or None),
    )
    conn.commit()


def ingest_directory(
    conn: sqlite3.Connection,
    directory: Path,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> IngestSummary:
    summary = IngestSummary(run_id=uuid.uuid4().hex[:8])
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"Data directory not found: {directory}")

    for path in sorted(p for p in directory.iterdir() if p.is_file() and not p.name.startswith(".")):
        name = path.name
        text, reason = read_and_validate(path)
        if text is None:
            summary.record(name, "rejected", reason or "")
            _log(conn, summary.run_id, name, "rejected", reason or "")
            continue

        content_hash = sha256(text)
        existing = conn.execute(
            "SELECT doc_id, content_hash FROM documents WHERE filename = ?", (name,)
        ).fetchone()
        if existing and existing["content_hash"] == content_hash:
            summary.record(name, "skipped_unchanged")
            _log(conn, summary.run_id, name, "skipped_unchanged")
            continue

        dup = conn.execute(
            "SELECT filename FROM documents WHERE content_hash = ? AND filename != ?",
            (content_hash, name),
        ).fetchone()
        if dup:
            reason = f"duplicate_content_of:{dup['filename']}"
            summary.record(name, "rejected", reason)
            _log(conn, summary.run_id, name, "rejected", reason)
            continue

        try:
            with conn:  # one transaction per file: all-or-nothing
                if existing:
                    _delete_document(conn, existing["doc_id"])
                n = _store_document(conn, name, text, content_hash, chunk_size, chunk_overlap)
            status = "updated" if existing else "ingested"
            summary.record(name, status, f"{n} chunks")
            _log(conn, summary.run_id, name, status, f"{n} chunks")
        except sqlite3.Error as exc:
            summary.record(name, "failed", str(exc))
            _log(conn, summary.run_id, name, "failed", str(exc))
    return summary
