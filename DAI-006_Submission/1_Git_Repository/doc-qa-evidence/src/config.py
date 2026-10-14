"""Settings loaded from environment variables (optionally from a .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

try:  # python-dotenv is optional at runtime
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


def _path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else PROJECT_ROOT / p


@dataclass(frozen=True)
class Settings:
    db_path: Path
    raw_data_dir: Path
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 3
    min_score: float = 0.60
    answer_provider: str = "extractive"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    provider_timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ.get
        return cls(
            db_path=_path(env("DB_PATH", "data/docqa.db")),
            raw_data_dir=_path(env("RAW_DATA_DIR", "data/raw")),
            chunk_size=int(env("CHUNK_SIZE", "500")),
            chunk_overlap=int(env("CHUNK_OVERLAP", "50")),
            top_k=int(env("TOP_K", "3")),
            min_score=float(env("MIN_SCORE", "0.60")),
            answer_provider=env("ANSWER_PROVIDER", "extractive").lower(),
            ollama_url=env("OLLAMA_URL", "http://localhost:11434"),
            ollama_model=env("OLLAMA_MODEL", "llama3.2"),
            provider_timeout=float(env("PROVIDER_TIMEOUT_SECONDS", "30")),
        )
