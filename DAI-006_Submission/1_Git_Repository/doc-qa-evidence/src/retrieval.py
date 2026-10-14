"""Keyword retrieval with SQLite FTS5 (BM25) plus a keyword-coverage evidence score."""
from __future__ import annotations

import re
import sqlite3

from .models import Chunk
from .textutil import STOPWORDS, keywords, stem, stem_set

_SQL = """
SELECT c.chunk_id, c.doc_id, d.filename, c.chunk_index, c.text, c.char_start, c.char_end,
       bm25(chunks_fts) AS bm25
FROM chunks_fts
JOIN chunks c    ON c.chunk_id = chunks_fts.chunk_id
JOIN documents d ON d.doc_id = c.doc_id
WHERE chunks_fts MATCH ?
ORDER BY bm25(chunks_fts)
LIMIT ?
"""


def build_match_query(kws: list[str]) -> str:
    """OR of quoted tokens. Tokens are [a-z0-9] only, so the expression is always valid."""
    return " OR ".join(f'"{k}"' for k in kws)


def retrieve(conn: sqlite3.Connection, question: str, top_k: int = 3, pool: int = 10) -> list[Chunk]:
    """Return up to top_k chunks ranked by keyword coverage, then BM25.

    coverage = share of the question's keywords present in the chunk (0..1). It is the
    evidence score: BM25 alone is relative (it always ranks *something* first), coverage
    tells us whether the chunk really contains what the question asks about.
    """
    kws = keywords(question)
    if not kws:
        return []
    kw_stems = {stem(k) for k in kws}
    rows = conn.execute(_SQL, (build_match_query(kws), pool)).fetchall()

    chunks = []
    for r in rows:
        coverage = len(kw_stems & stem_set(r["text"])) / len(kw_stems)
        chunks.append(
            Chunk(
                chunk_id=r["chunk_id"], doc_id=r["doc_id"], filename=r["filename"],
                chunk_index=r["chunk_index"], text=r["text"], char_start=r["char_start"],
                char_end=r["char_end"], bm25=-r["bm25"], coverage=round(coverage, 3),
            )
        )
    chunks.sort(key=lambda c: (-c.coverage, -c.bm25))
    return chunks[:top_k]


_ENTITY = re.compile(r"\b(?:[A-Z][A-Za-z0-9]+)\b")


def unknown_entities(conn: sqlite3.Connection, question: str) -> list[str]:
    """Capitalised terms in the question (names, products, acronyms) found in NO document.

    Keyword coverage alone is fooled by near-misses such as "Enterprise plan" when only a
    "Pro plan" exists. A proper noun that appears nowhere in the corpus means the question
    is about something the documents do not describe. The first word is skipped because
    sentences start with a capital letter anyway.
    """
    words = question.strip().split(None, 1)
    rest = words[1] if len(words) > 1 else ""
    missing = []
    for term in _ENTITY.findall(rest):
        token = term.lower()
        if token in STOPWORDS or token in missing:
            continue
        hit = conn.execute(
            "SELECT 1 FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT 1", (f'"{token}"',)
        ).fetchone()
        if hit is None:
            missing.append(token)
    return missing
