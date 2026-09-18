"""Factories for swappable local embeddings and later OpenRouter chat models."""

from __future__ import annotations

from pathlib import Path
import re

from langchain_classic.embeddings import CacheBackedEmbeddings
from langchain_classic.storage import LocalFileStore
from langchain_core.embeddings import Embeddings

from agent.lang import normalize_for_retrieval


DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-small"

def get_chat_model():
    """Create the OpenRouter chat client only when an agent turn needs it."""
    import os
    from langchain_openai import ChatOpenAI
    key = os.getenv("OPENROUTER_API_KEY"); model = os.getenv("LLM_MODEL")
    if not key or not model: raise RuntimeError("OPENROUTER_API_KEY and LLM_MODEL are required for live agent turns.")
    return ChatOpenAI(model=model, api_key=key, base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"), temperature=0)


class LocalMultilingualEmbeddings(Embeddings):
    """Sentence-transformers adapter with the required consistent Arabic normalization."""

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        normalized = [f"passage: {normalize_for_retrieval(text)}" for text in texts]
        vectors = self.model.encode(normalized, normalize_embeddings=True)
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        vector = self.model.encode(f"query: {normalize_for_retrieval(text)}", normalize_embeddings=True)
        return vector.tolist()


def get_embeddings(
    *,
    cache_dir: str | Path = "data/cache/embeddings",
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    cache_enabled: bool = True,
) -> Embeddings:
    """Return local multilingual embeddings, cached by normalized content hash on disk."""
    embeddings: Embeddings = LocalMultilingualEmbeddings(model_name)
    if not cache_enabled:
        return embeddings

    document_store = LocalFileStore(str(Path(cache_dir) / "documents"))
    query_store = LocalFileStore(str(Path(cache_dir) / "queries"))
    cache_namespace = re.sub(r"[^A-Za-z0-9._-]", "_", f"{model_name}_e5_prefixed_normalized_v2")
    return CacheBackedEmbeddings.from_bytes_store(
        embeddings,
        document_store,
        namespace=cache_namespace,
        query_embedding_cache=query_store,
        key_encoder="sha256",
    )
