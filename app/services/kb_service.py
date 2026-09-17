"""KnowledgeDocument write paths and their synchronous Chroma index updates."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from flask import current_app
from sqlalchemy import select

from agent.cache import RetrievalCache
from agent.llm import get_embeddings
from agent.rag import KnowledgeIndex
from app.extensions import db
from app.models import KnowledgeDocument


logger = logging.getLogger(__name__)
_index: KnowledgeIndex | None = None


def get_index() -> KnowledgeIndex:
    """Build the production index lazily so app startup does not download a model."""
    global _index
    if _index is None:
        _index = KnowledgeIndex(
            persist_directory=current_app.config["CHROMA_PERSIST_DIRECTORY"],
            embeddings=get_embeddings(),
            collection_name=current_app.config["RAG_COLLECTION_NAME"],
            retrieval_cache=RetrievalCache(ttl_seconds=current_app.config["RETRIEVAL_CACHE_TTL"]),
            score_floor=current_app.config["RAG_SCORE_FLOOR"],
        )
    return _index


def _sync_or_mark_unindexed(document: KnowledgeDocument, index: KnowledgeIndex) -> None:
    try:
        index.upsert_document(document)
        document.indexed_at = datetime.utcnow()
    except Exception:
        logger.exception("Knowledge document %s could not be indexed", document.id)
        document.indexed_at = None
        db.session.commit()
        raise
    db.session.commit()


def create_document(*, title: str, category: str, content: str, lang: str = "bilingual", active: bool = True, index: KnowledgeIndex | None = None) -> KnowledgeDocument:
    document = KnowledgeDocument(title=title, category=category, content=content, lang=lang, active=active)
    db.session.add(document)
    db.session.commit()
    active_index = index or get_index()
    if active:
        _sync_or_mark_unindexed(document, active_index)
    active_index.retrieval_cache.clear()
    return document


def update_document(document: KnowledgeDocument, *, index: KnowledgeIndex | None = None, **changes: Any) -> KnowledgeDocument:
    for field in ("title", "category", "content", "lang", "active"):
        if field in changes:
            setattr(document, field, changes[field])
    db.session.commit()
    active_index = index or get_index()
    if document.active:
        _sync_or_mark_unindexed(document, active_index)
    else:
        active_index.delete_document(document.id)
        document.indexed_at = None
        db.session.commit()
    active_index.retrieval_cache.clear()
    return document


def delete_document(document: KnowledgeDocument, *, index: KnowledgeIndex | None = None) -> None:
    active_index = index or get_index()
    active_index.delete_document(document.id)
    db.session.delete(document)
    db.session.commit()
    active_index.retrieval_cache.clear()


def toggle_active(document: KnowledgeDocument, *, active: bool, index: KnowledgeIndex | None = None) -> KnowledgeDocument:
    return update_document(document, active=active, index=index)


def reindex_all(*, index: KnowledgeIndex | None = None) -> int:
    active_index = index or get_index()
    documents = db.session.scalars(
        select(KnowledgeDocument).where(KnowledgeDocument.active.is_(True)).order_by(KnowledgeDocument.id)
    ).all()
    active_index.rebuild(documents)
    indexed_at = datetime.utcnow()
    for document in documents:
        document.indexed_at = indexed_at
    db.session.commit()
    active_index.retrieval_cache.clear()
    return len(documents)
