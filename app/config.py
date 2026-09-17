"""Environment-driven configuration shared by the Flask application and agent."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_flag(name: str, default: bool = False) -> bool:
    """Read a conventional boolean environment variable."""
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def database_url() -> str:
    """Resolve relative SQLite files from the repository root, not Flask's instance folder."""
    url = os.getenv("DATABASE_URL", "sqlite:///data/shifa.db")
    prefix = "sqlite:///"
    if url.startswith(prefix) and not url.startswith("sqlite:////"):
        relative_path = url.removeprefix(prefix)
        if relative_path != ":memory:":
            return f"sqlite:///{(BASE_DIR / relative_path).as_posix()}"
    return url


class Config:
    """Default configuration; secrets and deployment values come from the environment."""

    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = None

    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    LLM_MODEL = os.getenv("LLM_MODEL")
    LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL")

    CHROMA_PERSIST_DIRECTORY = os.getenv(
        "CHROMA_PERSIST_DIRECTORY", str(BASE_DIR / "data" / "chroma")
    )
    LLM_CACHE_ENABLED = env_flag("LLM_CACHE_ENABLED", True)
    LLM_CACHE_BACKEND = os.getenv("LLM_CACHE_BACKEND", "sqlite")
    LLM_CACHE_PATH = os.getenv("LLM_CACHE_PATH", str(BASE_DIR / "data" / "cache" / "llm.db"))
    LLM_CACHE_TTL = int(os.getenv("LLM_CACHE_TTL", "86400"))
    EMBEDDING_CACHE_ENABLED = env_flag("EMBEDDING_CACHE_ENABLED", True)
    RAG_COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "shifa_knowledge")
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
    RAG_SCORE_FLOOR = float(os.getenv("RAG_SCORE_FLOOR", "0.45"))
    RETRIEVAL_CACHE_TTL = int(os.getenv("RETRIEVAL_CACHE_TTL", "60"))

    META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")
    META_PAGE_ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN")
    META_APP_SECRET = os.getenv("META_APP_SECRET")
