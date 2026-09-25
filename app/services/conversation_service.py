"""Conversation persistence behind the agent's service boundary."""
from __future__ import annotations
from datetime import datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import Conversation, Customer, Message, MessengerEvent


def get_or_create_web_conversation(thread_id: str, customer_id: int | None = None) -> Conversation:
    conversation = db.session.scalar(select(Conversation).where(Conversation.external_thread_id == thread_id))
    if conversation is None:
        conversation = Conversation(channel="web", external_thread_id=thread_id, customer_id=customer_id)
        db.session.add(conversation)
        db.session.commit()
    return conversation


def upsert_chat_customer(
    full_name: str, phone: str, address: str, existing_customer_id: int | None = None
) -> Customer:
    """Create or refresh the customer record supplied during a chat checkout."""
    customer = db.session.get(Customer, existing_customer_id) if existing_customer_id else None
    by_phone = db.session.scalar(select(Customer).where(Customer.phone == phone))
    if customer is not None and by_phone is not None and by_phone.id != customer.id:
        # Messenger starts with a placeholder customer. If checkout supplies a
        # phone that already exists, transfer the PSID to that real record. The
        # placeholder must be cleared and flushed first or SQLite sees two
        # rows with the same unique external_id during the same commit.
        messenger_external_id = customer.external_id
        if messenger_external_id and by_phone.external_id in (None, messenger_external_id):
            customer.external_id = None
            db.session.flush()
            by_phone.external_id = messenger_external_id
        customer = by_phone
    elif customer is None:
        customer = by_phone
    if customer is None:
        customer = Customer(full_name=full_name, phone=phone, default_address=address)
        db.session.add(customer)
    else:
        customer.full_name = full_name
        customer.phone = phone
        customer.default_address = address
    db.session.commit()
    return customer


def attach_customer(conversation_id: int | None, customer_id: int) -> None:
    """Associate a checkout customer with its browser conversation when present."""
    if conversation_id is None:
        return
    conversation = db.session.get(Conversation, conversation_id)
    if conversation is not None and conversation.customer_id != customer_id:
        conversation.customer_id = customer_id
        db.session.commit()


def get_or_create_messenger_conversation(psid: str) -> Conversation:
    """Map a Facebook PSID to Customer.external_id and a stable graph thread."""
    customer = db.session.scalar(select(Customer).where(Customer.external_id == psid))
    if customer is None:
        placeholder_phone = f"msgr-{sha256(psid.encode('utf-8')).hexdigest()[:24]}"
        customer = Customer(full_name="Messenger customer", phone=placeholder_phone, external_id=psid)
        db.session.add(customer)
        db.session.flush()
    thread_id = f"messenger:{psid}"
    conversation = db.session.scalar(select(Conversation).where(Conversation.external_thread_id == thread_id))
    if conversation is None:
        conversation = Conversation(channel="messenger", external_thread_id=thread_id, customer_id=customer.id)
        db.session.add(conversation)
    elif conversation.customer_id != customer.id:
        conversation.customer_id = customer.id
    db.session.commit()
    return conversation


def claim_messenger_event(event_id: str) -> bool:
    """Return true once only, even when Meta retries the same message event."""
    try:
        # Legacy helper retained for callers that only need an id claim.
        db.session.add(MessengerEvent(event_id=event_id, psid="", text="", status="done"))
        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        return False


def enqueue_messenger_event(event_id: str, psid: str, text: str) -> bool:
    """Persist a Messenger event before acknowledging Meta's webhook POST."""
    try:
        db.session.add(MessengerEvent(event_id=event_id, psid=psid, text=text, status="pending"))
        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        return False


def pending_messenger_event_ids() -> list[str]:
    events = db.session.scalars(
        select(MessengerEvent).where(MessengerEvent.status == "pending").order_by(MessengerEvent.received_at)
    ).all()
    return [event.event_id for event in events]


def mark_messenger_processing(event_id: str) -> MessengerEvent | None:
    claimed = db.session.execute(
        update(MessengerEvent)
        .where(MessengerEvent.event_id == event_id, MessengerEvent.status == "pending")
        .values(status="processing", attempts=MessengerEvent.attempts + 1)
    )
    if claimed.rowcount != 1:
        db.session.rollback()
        return None
    db.session.commit()
    return db.session.scalar(select(MessengerEvent).where(MessengerEvent.event_id == event_id))


def reset_processing_messenger_events() -> None:
    """Make rows interrupted by a process restart eligible again."""
    db.session.execute(update(MessengerEvent).where(MessengerEvent.status == "processing").values(status="pending"))
    db.session.commit()


def mark_messenger_done(event_id: str) -> None:
    event = db.session.scalar(select(MessengerEvent).where(MessengerEvent.event_id == event_id))
    if event:
        event.status, event.processed_at, event.last_error = "done", datetime.utcnow(), None
        db.session.commit()


def mark_messenger_retry(event_id: str, error: str) -> None:
    event = db.session.scalar(select(MessengerEvent).where(MessengerEvent.event_id == event_id))
    if event:
        event.status, event.last_error = "pending", error[:1000]
        db.session.commit()


def customer_context(customer_id: int | None) -> dict[str, Any]:
    customer = db.session.get(Customer, customer_id) if customer_id else None
    return {"customer_id": customer.id if customer else None, "customer_ref": customer.phone if customer else None,
            "customer_address": customer.default_address if customer else None}


def persist_messages(conversation_id: int, messages: list[dict[str, str]], meta: dict[str, Any]) -> None:
    for message in messages:
        db.session.add(Message(conversation_id=conversation_id, role=message["role"], content=message["content"], meta=meta))
    db.session.commit()


def list_conversations() -> list[Conversation]:
    return db.session.scalars(select(Conversation).order_by(Conversation.updated_at.desc())).all()


def conversation_with_messages(conversation_id: int) -> Conversation | None:
    return db.session.get(Conversation, conversation_id)
