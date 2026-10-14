"""Default provider: no model. Returns the sentence that best matches the question."""
from __future__ import annotations

from ..models import Chunk, ProviderResult
from ..textutil import keywords, split_sentences, stem, stem_set
from .base import AnswerProvider


class ExtractiveProvider(AnswerProvider):
    name = "extractive"

    def answer(self, question: str, chunks: list[Chunk]) -> ProviderResult:
        kw_stems = {stem(k) for k in keywords(question)}
        best_score, best_sentence, best_chunk = 0, None, None
        for chunk in chunks:                       # chunks arrive best-first, so ties favour rank
            for sentence in split_sentences(chunk.text):
                score = len(kw_stems & stem_set(sentence))
                if score > best_score:
                    best_score, best_sentence, best_chunk = score, sentence, chunk
        if best_sentence is None:
            return ProviderResult(answer=None, insufficient=True, provider=self.name)
        return ProviderResult(
            answer=best_sentence, chunk_id=best_chunk.chunk_id, provider=self.name
        )
