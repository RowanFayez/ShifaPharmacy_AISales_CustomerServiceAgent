import hashlib
import hmac
import json

from sqlalchemy import select

from app.extensions import db
from app.models import Conversation, Customer, MessengerEvent


def _configure_messenger(app):
    app.config.update(
        META_VERIFY_TOKEN="verify-test-token",
        META_PAGE_ACCESS_TOKEN="page-test-token",
        META_APP_SECRET="app-test-secret",
        META_GRAPH_API_VERSION="v22.0",
    )


def _signed_body(payload: dict) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(b"app-test-secret", raw, hashlib.sha256).hexdigest()
    return raw, {"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={signature}"}


def test_webhook_is_gracefully_disabled_without_credentials(client):
    response = client.get("/webhook?hub.mode=subscribe&hub.verify_token=anything&hub.challenge=abc")
    assert response.status_code == 503


def test_webhook_verification_requires_the_configured_token(client, app):
    _configure_messenger(app)
    accepted = client.get("/webhook?hub.mode=subscribe&hub.verify_token=verify-test-token&hub.challenge=challenge-123")
    rejected = client.get("/webhook?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=challenge-123")
    assert accepted.status_code == 200 and accepted.get_data(as_text=True) == "challenge-123"
    assert rejected.status_code == 403


def test_messenger_event_is_signed_async_deduplicated_and_maps_psid(client, app, monkeypatch):
    _configure_messenger(app)
    from app.blueprints import webhook as webhook_module
    from app.services import messenger_service

    invoked, sent = [], []

    class InlineExecutor:
        def submit(self, function, *args, **kwargs):
            function(*args, **kwargs)

    monkeypatch.setattr(webhook_module, "MESSENGER_EXECUTOR", InlineExecutor())
    monkeypatch.setattr(
        messenger_service,
        "_invoke_agent",
        lambda conversation_id, customer_id, psid, text: invoked.append((conversation_id, customer_id, psid, text)) or {"response": "Available now."},
    )
    monkeypatch.setattr(messenger_service, "_send_text", lambda config, psid, text: sent.append((psid, text)))
    payload = {
        "object": "page",
        "entry": [{"messaging": [{"sender": {"id": "PSID-123"}, "recipient": {"id": "PAGE-1"}, "message": {"mid": "mid.abc", "text": "Do you have Panadol?"}}]}],
    }
    raw, headers = _signed_body(payload)
    first = client.post("/webhook", data=raw, headers=headers)
    duplicate = client.post("/webhook", data=raw, headers=headers)

    assert first.status_code == duplicate.status_code == 200
    assert first.get_json() == {"status": "EVENT_RECEIVED"}
    assert len(invoked) == 1 and sent == [("PSID-123", "Available now.")]
    with app.app_context():
        customer = db.session.scalar(select(Customer).where(Customer.external_id == "PSID-123"))
        conversation = db.session.scalar(select(Conversation).where(Conversation.external_thread_id == "messenger:PSID-123"))
        assert customer is not None and conversation is not None
        assert conversation.customer_id == customer.id and conversation.channel == "messenger"
        assert db.session.scalar(select(MessengerEvent).where(MessengerEvent.event_id == "mid.abc")) is not None


def test_messenger_rejects_bad_signature_and_ignores_echoes(client, app, monkeypatch):
    _configure_messenger(app)
    from app.blueprints import webhook as webhook_module

    class FailingExecutor:
        def submit(self, *_args, **_kwargs):
            raise AssertionError("echoes must not be queued")

    monkeypatch.setattr(webhook_module, "MESSENGER_EXECUTOR", FailingExecutor())
    payload = {"object": "page", "entry": [{"messaging": [{"sender": {"id": "PAGE-1"}, "message": {"mid": "mid.echo", "text": "sent reply", "is_echo": True}}]}]}
    raw, headers = _signed_body(payload)
    rejected = client.post("/webhook", data=raw, headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=wrong"})
    echo = client.post("/webhook", data=raw, headers=headers)
    assert rejected.status_code == 403
    assert echo.status_code == 200


def test_messenger_checkout_merges_placeholder_into_existing_phone_customer(app, pharmacy_data):
    from app.services import conversation_service

    with app.app_context():
        conversation = conversation_service.get_or_create_messenger_conversation("PSID-CHECKOUT")
        customer = conversation_service.upsert_chat_customer(
            "Sama Fayez", "01012345678", "Agami Abu Yousef", conversation.customer_id
        )
        conversation_service.attach_customer(conversation.id, customer.id)
        assert customer.id == pharmacy_data["customer_id"]
        assert customer.external_id == "PSID-CHECKOUT"
        assert conversation_service.get_or_create_messenger_conversation("PSID-CHECKOUT").customer_id == customer.id


def test_checkout_details_accept_labels_without_colons_and_arabic_phone(app):
    from agent.nodes.order_details import _parse_details

    with app.app_context():
        details = _parse_details("الاسم سما فايز\nالموبايل 01123649958\nالعنوان العجمي ابويوسف")
    assert details == {"name": "سما فايز", "phone": "01123649958", "address": "العجمي ابويوسف"}


def test_checkout_details_accepts_natural_conversational_message(app):
    from agent.nodes.order_details import _parse_details

    with app.app_context():
        details = _parse_details("أنا سما فايز، رقمي 01123649958، ساكنة في العجمي ابويوسف")
    assert details == {"name": "سما فايز", "phone": "01123649958", "address": "العجمي ابويوسف"}
