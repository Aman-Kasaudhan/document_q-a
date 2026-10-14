"""Question answering with an evidence gate.

Flow: retrieve -> evidence check (score >= MIN_SCORE) -> provider -> answer + source chunk,
otherwise 'insufficient_evidence'. Every question is written to query_log.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from .config import Settings
from .models import Answer, Chunk
from .providers import AnswerProvider, ExtractiveProvider, ProviderError, get_provider
from .retrieval import retrieve, unknown_entities

INSUFFICIENT_MESSAGE = "Insufficient evidence: the documents do not contain enough information to answer this question."


class QAService:
    def __init__(self, conn: sqlite3.Connection, settings: Settings,
                 provider: Optional[AnswerProvider] = None,
                 fallback: Optional[AnswerProvider] = None):
        self.conn = conn
        self.settings = settings
        self.provider = provider or get_provider(settings)
        self.fallback = fallback or ExtractiveProvider()

    def ask(self, question: str) -> Answer:
        question = (question or "").strip()
        if not question:
            return self._finish(Answer(question, "insufficient_evidence", None, 0.0, "none",
                                       note="empty_question"))

        chunks = retrieve(self.conn, question, self.settings.top_k)
        top_score = chunks[0].coverage if chunks else 0.0

        if not chunks:
            return self._finish(Answer(question, "insufficient_evidence", None, 0.0, "none",
                                       note="no_matching_chunks"))
        if top_score < self.settings.min_score:
            return self._finish(Answer(
                question, "insufficient_evidence", None, top_score, "none", sources=chunks,
                note=f"evidence_below_threshold:{top_score:.2f}<{self.settings.min_score:.2f}"))

        missing = unknown_entities(self.conn, question)
        if missing:
            return self._finish(Answer(
                question, "insufficient_evidence", None, top_score, "none", sources=chunks,
                note="unknown_entity_not_in_documents:" + ",".join(missing)))

        note = ""
        try:
            result = self.provider.answer(question, chunks)
        except ProviderError as exc:
            note = f"provider_failed_fallback_used:{exc}"
            result = self.fallback.answer(question, chunks)

        if result.insufficient or not result.answer:
            return self._finish(Answer(
                question, "insufficient_evidence", None, top_score, result.provider, sources=chunks,
                note=(note + "; " if note else "") + "provider_found_no_supporting_text"))

        return self._finish(Answer(
            question, "answered", result.answer, top_score, result.provider, note=note,
            primary_chunk_id=result.chunk_id or chunks[0].chunk_id, sources=chunks))

    def _finish(self, ans: Answer) -> Answer:
        self.conn.execute(
            "INSERT INTO query_log (question, status, answer, top_score, chunk_ids, provider, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ans.question, ans.status, ans.answer, ans.top_score,
             ",".join(str(c.chunk_id) for c in ans.sources), ans.provider, ans.note or None),
        )
        self.conn.commit()
        return ans
