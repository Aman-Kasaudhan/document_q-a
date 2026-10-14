"""Optional provider: a local LLM served by Ollama (free, no API key).

Safety rules enforced here:
  * the prompt allows only the supplied context and defines an explicit refusal token;
  * the model must cite the chunk it used as [n]; an answer without a valid citation is
    treated as malformed (ProviderError) so the caller falls back to the extractive provider;
  * network errors, non-200 responses, bad JSON and empty output all raise ProviderError.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from ..models import Chunk, ProviderResult
from .base import AnswerProvider, ProviderError

REFUSAL_TOKEN = "INSUFFICIENT_EVIDENCE"

PROMPT = """You answer questions using ONLY the numbered context passages below.
Rules:
- If the passages do not contain the answer, reply with exactly: {refusal}
- Otherwise answer in one or two sentences and end with the passage number you used, like [2].
- Never use outside knowledge.

Context:
{context}

Question: {question}
Answer:"""


def _default_post(*args, **kwargs):
    import requests  # imported lazily so the default setup does not need it

    return requests.post(*args, **kwargs)


class OllamaProvider(AnswerProvider):
    name = "ollama"

    def __init__(self, url: str, model: str, timeout: float = 30.0,
                 http_post: Optional[Callable] = None):
        self.url, self.model, self.timeout = url.rstrip("/"), model, timeout
        self._post = http_post or _default_post

    def build_prompt(self, question: str, chunks: list[Chunk]) -> str:
        context = "\n\n".join(f"[{i}] ({c.filename}) {c.text}" for i, c in enumerate(chunks, 1))
        return PROMPT.format(refusal=REFUSAL_TOKEN, context=context, question=question)

    def answer(self, question: str, chunks: list[Chunk]) -> ProviderResult:
        payload = {
            "model": self.model,
            "prompt": self.build_prompt(question, chunks),
            "stream": False,
            "options": {"temperature": 0},
        }
        try:
            resp = self._post(f"{self.url}/api/generate", json=payload, timeout=self.timeout)
        except Exception as exc:  # timeout, connection refused, ...
            raise ProviderError(f"request failed: {exc.__class__.__name__}: {exc}") from exc

        if getattr(resp, "status_code", 200) != 200:
            raise ProviderError(f"unexpected HTTP status {resp.status_code}")
        try:
            text = str(resp.json()["response"]).strip()
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError("malformed JSON response") from exc
        if not text:
            raise ProviderError("empty model response")

        if REFUSAL_TOKEN in text.upper().replace(" ", "_"):
            return ProviderResult(answer=None, insufficient=True, provider=self.name)

        cited = [int(n) for n in re.findall(r"\[(\d+)\]", text) if 1 <= int(n) <= len(chunks)]
        if not cited:
            raise ProviderError("answer has no valid citation")
        answer = re.sub(r"\s*\[\d+\]", "", text).strip()
        if not answer:
            raise ProviderError("answer empty after removing citation")
        return ProviderResult(
            answer=answer, chunk_id=chunks[cited[-1] - 1].chunk_id, provider=self.name
        )
