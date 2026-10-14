"""Plain data containers shared across modules."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class Chunk:
    chunk_id: int
    doc_id: int
    filename: str
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    bm25: float = 0.0       # relevance from FTS5 (higher = better)
    coverage: float = 0.0   # share of question keywords found in this chunk (0..1)


@dataclass
class ProviderResult:
    """What an AnswerProvider returns. chunk_id says which chunk supports the answer."""
    answer: Optional[str]
    insufficient: bool = False
    chunk_id: Optional[int] = None
    provider: str = ""


@dataclass
class Answer:
    question: str
    status: str                      # "answered" | "insufficient_evidence"
    answer: Optional[str]
    top_score: float
    provider: str
    note: str = ""
    primary_chunk_id: Optional[int] = None
    sources: list[Chunk] = field(default_factory=list)

    @property
    def primary_source(self) -> Optional[Chunk]:
        for c in self.sources:
            if c.chunk_id == self.primary_chunk_id:
                return c
        return None

    def to_dict(self) -> dict:
        return asdict(self)
