"""The single seam between retrieval and any answer generator (extractive or LLM)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Chunk, ProviderResult


class ProviderError(Exception):
    """Raised when a provider fails or returns an unusable response (timeout, bad output...)."""


class AnswerProvider(ABC):
    name: str = "base"

    @abstractmethod
    def answer(self, question: str, chunks: list[Chunk]) -> ProviderResult:
        """Answer using ONLY the given chunks.

        Return ProviderResult(insufficient=True) if the chunks do not support an answer.
        Raise ProviderError for failures / malformed output so the caller can fall back.
        """
