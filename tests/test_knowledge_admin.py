from __future__ import annotations

from agent.cache import RetrievalCache
from agent.lang import normalize_for_retrieval
from agent.rag import KnowledgeIndex
from app.extensions import db
from app.models import KnowledgeDocument
from app.services import kb_service


class FakeEmbeddings:
    """Offline deterministic embeddings for admin integration tests."""

    dimensions = 128

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in normalize_for_retrieval(text).split():
            vector[sum(ord(char) for char in token) % self.dimensions] += 1.0
        return vector


def make_index(tmp_path) -> KnowledgeIndex:
    return KnowledgeIndex(
        tmp_path / "knowledge_admin_chroma",
        FakeEmbeddings(),
        collection_name="knowledge_admin",
        retrieval_cache=RetrievalCache(ttl_seconds=300),
        score_floor=0.10,
    )


def test_knowledge_admin_crud_and_reindex(client, app, tmp_path, monkeypatch):
    index = make_index(tmp_path)
    monkeypatch.setattr(kb_service, "get_index", lambda: index)

    response = client.get("/admin/knowledge/new")
    assert response.status_code == 200
    assert b"New knowledge document" in response.data

    response = client.post(
        "/admin/knowledge/new",
        data={"title": "", "category": "delivery", "lang": "bilingual", "content": ""},
    )
    assert response.status_code == 200
    assert response.data.count(b"This field is required.") == 2

    response = client.post(
        "/admin/knowledge/new",
        data={
            "title": "Weekend delivery",
            "category": "delivery",
            "lang": "bilingual",
            "content": "English: Friday delivery closes at 8 PM. العربية: التوصيل يوم الجمعة حتى الساعة 8 مساءً.",
            "active": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Knowledge document created and indexed." in response.data
    assert b"Indexed" in response.data

    with app.app_context():
        document = db.session.query(KnowledgeDocument).filter_by(title="Weekend delivery").one()
        document_id = document.id
        assert document.indexed_at is not None

    response = client.get(f"/admin/knowledge/{document_id}/edit")
    assert response.status_code == 200
    assert b"Edit knowledge document" in response.data

    response = client.post(
        f"/admin/knowledge/{document_id}/edit",
        data={
            "title": "Weekend delivery",
            "category": "delivery",
            "lang": "bilingual",
            "content": "English: Friday delivery closes at 9 PM. العربية: التوصيل يوم الجمعة حتى الساعة 9 مساءً.",
            "active": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Knowledge document updated and index synchronized." in response.data
    assert index.retrieve("Friday delivery 9 PM")[0]["metadata"]["doc_id"] == str(document_id)

    response = client.post("/admin/knowledge/reindex", follow_redirects=True)
    assert response.status_code == 200
    assert b"Reindexed 1 active knowledge documents." in response.data

    response = client.post(f"/admin/knowledge/{document_id}/delete", follow_redirects=True)
    assert response.status_code == 200
    assert b"Knowledge document deleted." in response.data
    with app.app_context():
        assert db.session.get(KnowledgeDocument, document_id) is None
    assert index.retrieve("Friday delivery") == []


def test_knowledge_admin_shows_needs_reindex_status(client, app):
    with app.app_context():
        db.session.add(
            KnowledgeDocument(
                title="Unindexed policy",
                category="policy",
                lang="en",
                content="A document awaiting index repair.",
                active=True,
            )
        )
        db.session.commit()

    response = client.get("/admin/knowledge")
    assert response.status_code == 200
    assert b"Unindexed policy" in response.data
    assert b"Needs reindex" in response.data
