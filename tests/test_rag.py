from __future__ import annotations

from pathlib import Path

from agent.cache import RetrievalCache
from agent.lang import normalize_arabic, normalize_for_retrieval
from agent.rag import KnowledgeIndex
from app.extensions import db
from app.models import KnowledgeDocument
from app.services import kb_service


class FakeEmbeddings:
    """Deterministic offline embeddings: tests never download the real model."""

    dimensions = 128

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in normalize_for_retrieval(text).split():
            vector[sum(ord(char) for char in token) % self.dimensions] += 1.0
        return vector


def make_index(path: Path, collection: str) -> KnowledgeIndex:
    return KnowledgeIndex(
        path,
        FakeEmbeddings(),
        collection_name=collection,
        retrieval_cache=RetrievalCache(ttl_seconds=300),
        score_floor=0.10,
    )


def test_arabic_normalization_is_consistent():
    assert normalize_arabic("إِنـهَى") == "انهي"
    assert normalize_for_retrieval("بَانـادول") == normalize_for_retrieval("بانادول")


def test_kb_update_invalidates_cached_retrieval(app, tmp_path):
    with app.app_context():
        index = make_index(tmp_path / "chroma", "kb_update")
        document = kb_service.create_document(
            title="Delivery policy",
            category="delivery",
            content="English delivery fee is EGP 35. العربية رسوم التوصيل 35 جنيه.",
            index=index,
        )

        initial = index.retrieve("delivery fee")
        assert initial and "EGP 35" in initial[0]["content"]
        assert index.retrieval_cache.entry_count == 1

        kb_service.update_document(
            document,
            content="English returns are accepted for 30 days. العربية الاسترجاع خلال 30 يوم.",
            index=index,
        )
        updated = index.retrieve("returns 30 days")

        assert updated and "30 days" in updated[0]["content"]
        assert "delivery fee" not in updated[0]["content"]
        assert document.indexed_at is not None


def test_multilingual_retrieval_returns_the_same_document(app, tmp_path):
    with app.app_context():
        index = make_index(tmp_path / "chroma", "kb_multilingual")
        document = kb_service.create_document(
            title="Cairo delivery",
            category="delivery",
            content="English: delivery is available in Cairo. العربية: التوصيل متاح داخل القاهرة.",
            index=index,
        )

        english = index.retrieve("Is delivery available in Cairo?")
        arabic = index.retrieve("هل التوصيل متاح في القاهرة؟")
        masri = index.retrieve("التوصيل للقاهرة متاح يا اسطا؟")

        assert {result[0]["metadata"]["doc_id"] for result in (english, arabic, masri)} == {str(document.id)}


def test_toggle_delete_and_reindex_keep_chroma_in_sync(app, tmp_path):
    with app.app_context():
        index = make_index(tmp_path / "chroma", "kb_sync")
        document = kb_service.create_document(
            title="Payment methods",
            category="payments",
            content="English: cash on delivery is available. العربية: الدفع عند الاستلام متاح.",
            index=index,
        )
        assert index.retrieve("cash delivery")

        kb_service.toggle_active(document, active=False, index=index)
        assert index.retrieve("cash delivery") == []

        kb_service.toggle_active(document, active=True, index=index)
        assert index.retrieve("cash delivery")
        assert kb_service.reindex_all(index=index) == 1

        kb_service.delete_document(document, index=index)
        assert db.session.get(KnowledgeDocument, document.id) is None
        assert index.retrieve("cash delivery") == []
