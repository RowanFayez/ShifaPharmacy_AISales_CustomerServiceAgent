"""Persistent Chroma knowledge index derived from `KnowledgeDocument` rows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from agent.cache import RetrievalCache


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    content: str
    metadata: dict[str, Any]


def chunk_document(document: Any) -> list[KnowledgeChunk]:
    """Split Markdown headers first, then produce deterministic ~600-character chunks."""
    header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "h1"), ("##", "h2")])
    header_sections = header_splitter.split_text(document.content)
    splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=80)
    chunks: list[KnowledgeChunk] = []
    for section in header_sections or []:
        for piece in splitter.split_text(section.page_content):
            chunks.append(
                KnowledgeChunk(
                    id=f"{document.id}:{len(chunks)}",
                    content=piece,
                    metadata={
                        "doc_id": str(document.id),
                        "title": document.title,
                        "category": document.category,
                        "lang": document.lang,
                        "chunk_index": len(chunks),
                    },
                )
            )
    if not chunks and document.content.strip():
        chunks.append(
            KnowledgeChunk(
                id=f"{document.id}:0",
                content=document.content,
                metadata={
                    "doc_id": str(document.id),
                    "title": document.title,
                    "category": document.category,
                    "lang": document.lang,
                    "chunk_index": 0,
                },
            )
        )
    return chunks


class KnowledgeIndex:
    """A rebuildable Chroma index; SQL remains the source of truth."""

    def __init__(
        self,
        persist_directory: str | Path,
        embeddings: Embeddings,
        *,
        collection_name: str = "shifa_knowledge",
        retrieval_cache: RetrievalCache | None = None,
        score_floor: float = 0.45,
    ) -> None:
        self.client = chromadb.PersistentClient(path=str(persist_directory))
        self.collection_name = collection_name
        self.embeddings = embeddings
        self.retrieval_cache = retrieval_cache or RetrievalCache()
        self.score_floor = score_floor
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _fresh_collection(self) -> None:
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_document(self, document: Any) -> None:
        chunks = chunk_document(document)
        self.delete_document(document.id, clear_cache=False)
        if chunks:
            self.collection.add(
                ids=[chunk.id for chunk in chunks],
                documents=[chunk.content for chunk in chunks],
                metadatas=[chunk.metadata for chunk in chunks],
                embeddings=self.embeddings.embed_documents([chunk.content for chunk in chunks]),
            )
        self.retrieval_cache.clear()

    def delete_document(self, document_id: int, *, clear_cache: bool = True) -> None:
        self.collection.delete(where={"doc_id": str(document_id)})
        if clear_cache:
            self.retrieval_cache.clear()

    def rebuild(self, documents: list[Any]) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except ValueError:
            pass
        self._fresh_collection()
        for document in documents:
            self.upsert_document(document)
        self.retrieval_cache.clear()

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 4,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        cached = self.retrieval_cache.get(query, metadata_filter, top_k)
        if cached is not None:
            return cached

        if self.collection.count() == 0:
            self.retrieval_cache.set(query, metadata_filter, top_k, [])
            return []
        result = self.collection.query(
            query_embeddings=[self.embeddings.embed_query(query)],
            n_results=min(top_k, self.collection.count()),
            where=metadata_filter,
            include=["documents", "metadatas", "distances"],
        )
        retrieved: list[dict[str, Any]] = []
        for document, metadata, distance in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0], strict=True
        ):
            score = 1 - float(distance)
            if score >= self.score_floor:
                retrieved.append({"content": document, "metadata": metadata, "score": score})
        self.retrieval_cache.set(query, metadata_filter, top_k, retrieved)
        return retrieved
