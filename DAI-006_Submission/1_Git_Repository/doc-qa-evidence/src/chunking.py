"""Paragraph-aware chunking with character offsets and a small character overlap."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str
    start: int   # offset into the (normalised) document text
    end: int


_PARAGRAPH = re.compile(r"[^\n]+(?:\n[^\n]+)*")
_SENTENCE_GAP = re.compile(r"(?<=[.!?])\s+")


def normalise(text: str) -> str:
    """Consistent line endings/whitespace so hashes and offsets are stable."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_span(text: str, start: int, end: int, size: int) -> list[tuple[int, int]]:
    """Break an oversized paragraph into sentence-sized (or word-sized) pieces."""
    if end - start <= size:
        return [(start, end)]
    pieces, cur = [], start
    for m in _SENTENCE_GAP.finditer(text, start, end):
        pieces.append((cur, m.start()))
        cur = m.end()
    pieces.append((cur, end))
    out: list[tuple[int, int]] = []
    for s, e in pieces:
        while e - s > size:
            cut = text.rfind(" ", s, s + size)
            if cut <= s:
                cut = s + size
            out.append((s, cut))
            s = cut
            while s < e and text[s].isspace():
                s += 1
        if e > s:
            out.append((s, e))
    return out


def chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[TextChunk]:
    """Pack paragraphs into chunks of roughly `size` characters.

    Consecutive chunks share up to `overlap` characters (snapped to a word start) so a
    sentence on a boundary is still found whole in at least one chunk.
    """
    if size <= 0:
        raise ValueError("chunk size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be >= 0 and smaller than chunk size")

    units: list[tuple[int, int]] = []
    for m in _PARAGRAPH.finditer(text):
        units.extend(_split_span(text, m.start(), m.end(), size))
    if not units:
        return []

    chunks: list[TextChunk] = []
    i, start, n = 0, units[0][0], len(units)
    while i < n:
        j = i
        while j + 1 < n and units[j + 1][1] - start <= size:
            j += 1
        end = units[j][1]
        raw = text[start:end]
        lead = len(raw) - len(raw.lstrip())
        chunks.append(TextChunk(len(chunks), raw.strip(), start + lead, end))
        if j == n - 1:
            break
        nxt = units[j + 1][0]
        cand = end - overlap if overlap else nxt
        while cand < nxt and cand > 0 and not text[cand - 1].isspace():
            cand += 1                      # snap forward to a word start
        i, start = j + 1, min(cand, nxt)
    return chunks
