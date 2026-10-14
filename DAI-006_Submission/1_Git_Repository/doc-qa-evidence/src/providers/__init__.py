from ..config import Settings
from .base import AnswerProvider, ProviderError
from .extractive import ExtractiveProvider
from .ollama import OllamaProvider


def get_provider(settings: Settings) -> AnswerProvider:
    """Factory: the only place that knows which concrete provider is configured."""
    if settings.answer_provider == "ollama":
        return OllamaProvider(settings.ollama_url, settings.ollama_model, settings.provider_timeout)
    if settings.answer_provider == "extractive":
        return ExtractiveProvider()
    raise ValueError(f"Unknown ANSWER_PROVIDER: {settings.answer_provider!r}")


__all__ = ["AnswerProvider", "ProviderError", "ExtractiveProvider", "OllamaProvider", "get_provider"]
