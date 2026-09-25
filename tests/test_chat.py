from app.extensions import db
from app.models import Conversation, Handoff, Message


def test_chat_api_persists_safe_turn_and_admin_can_view_it(client, app):
    response = client.post("/api/chat", json={"message": "Please diagnose my symptoms"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert "pharmacist" in data["reply"].casefold()
    with app.app_context():
        conversation = db.session.get(Conversation, data["conversation_id"])
        assert conversation is not None
        assert [message.role for message in conversation.messages] == ["user", "assistant"]
        assert conversation.messages[-1].meta["intent"] == "safety"
        assert db.session.query(Handoff).filter_by(conversation_id=conversation.id).count() == 1
    assert client.get("/admin/conversations").status_code == 200
    assert client.get(f"/admin/conversations/{data['conversation_id']}").status_code == 200
    assert client.get("/admin/handoffs").status_code == 200


def test_chat_api_validates_payload(client):
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_chat_page_has_no_demo_customer_phone_field(client):
    response = client.get("/chat")
    assert response.status_code == 200
    assert "customer-phone" not in response.get_data(as_text=True)
    assert "demo customer" not in response.get_data(as_text=True).casefold()


def test_chat_api_does_not_require_a_demo_customer_phone(client, app, monkeypatch):
    class FakeGraph:
        def invoke(self, state, config):
            assert state["customer_id"] is None
            return {"response": "Chat response", "language": "en"}
    monkeypatch.setattr("app.blueprints.chat.build_graph", lambda: FakeGraph())
    response = client.post("/api/chat", json={"message": "Hello"})
    assert response.status_code == 200 and response.get_json()["ok"] is True


def test_meta_required_public_policy_pages(client):
    policy = client.get("/privacy-policy")
    deletion = client.get("/data-deletion")
    assert policy.status_code == deletion.status_code == 200
    assert "Privacy Policy" in policy.get_data(as_text=True)
    assert "Data Deletion" in deletion.get_data(as_text=True)
