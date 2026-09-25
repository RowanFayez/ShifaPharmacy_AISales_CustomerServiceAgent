"""Meta Messenger transport and asynchronous agent invocation."""
from __future__ import annotations

import hashlib
import hmac
import inspect
import json
import logging
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask
from langchain_core.messages import HumanMessage

from app.services import conversation_service


LOGGER = logging.getLogger(__name__)


def is_configured(config: dict[str, Any]) -> bool:
    return all(config.get(key) for key in ("META_VERIFY_TOKEN", "META_PAGE_ACCESS_TOKEN", "META_APP_SECRET"))


def valid_signature(raw_body: bytes, signature: str | None, app_secret: str | None) -> bool:
    if not signature or not app_secret or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _send_text(config: dict[str, Any], psid: str, text: str) -> None:
    version = config.get("META_GRAPH_API_VERSION", "v22.0")
    url = f"https://graph.facebook.com/{version}/me/messages?access_token={config['META_PAGE_ACCESS_TOKEN']}"
    payload = json.dumps(
        {"recipient": {"id": psid}, "messaging_type": "RESPONSE", "message": {"text": text}}
    ).encode("utf-8")
    request = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=float(config.get("META_REQUEST_TIMEOUT", 10))) as response:
            if response.status >= 300:
                raise RuntimeError(f"Messenger send returned HTTP {response.status}")
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError("Messenger send failed") from error


def _invoke_agent(conversation_id: int, customer_id: int | None, psid: str, text: str, *, is_first_turn: bool = False) -> dict[str, Any]:
    # Import lazily to avoid the Flask application-factory import cycle.
    from agent.graph import build_graph

    return build_graph().invoke(
        {"messages": [HumanMessage(content=text)], "conversation_id": conversation_id, "customer_id": customer_id,
         "is_first_turn": is_first_turn, "channel": "messenger"},
        config={"configurable": {"thread_id": f"messenger:{psid}"}},
    )


def process_messenger_event(app: Flask, event_id: str) -> None:
    """Process one durable inbox row; failures remain pending for retry."""
    with app.app_context():
        event = conversation_service.mark_messenger_processing(event_id)
        if event is None:
            return
        try:
            conversation = conversation_service.get_or_create_messenger_conversation(event.psid)
            is_first_turn = not bool(conversation.messages)
            if "is_first_turn" in inspect.signature(_invoke_agent).parameters:
                result = _invoke_agent(conversation.id, conversation.customer_id, event.psid, event.text, is_first_turn=is_first_turn)
            else:  # backwards-compatible test/integration doubles
                result = _invoke_agent(conversation.id, conversation.customer_id, event.psid, event.text)
            reply = str(result.get("response") or "I'm unable to respond right now. Please contact the pharmacy.")
            _send_text(app.config, event.psid, reply[:2000])
            conversation_service.mark_messenger_done(event_id)
        except Exception as error:
            conversation_service.mark_messenger_retry(event_id, str(error))
            LOGGER.exception("Messenger event processing failed; queued for retry")


def process_incoming_event(app: Flask, event: dict[str, Any]) -> None:
    """Persist before returning HTTP 200; processing can safely happen later."""
    messaging = event.get("messaging") or {}
    message = messaging.get("message") or {}
    psid = str((messaging.get("sender") or {}).get("id") or "")
    text = str(message.get("text") or "").strip()
    message_id = str(message.get("mid") or "")
    if not psid or not text or not message_id or message.get("is_echo"):
        return
    with app.app_context():
        inserted = conversation_service.enqueue_messenger_event(message_id, psid, text)
    if inserted:
        process_messenger_event(app, message_id)


def start_retry_worker(app: Flask) -> None:
    """Replay pending inbox rows after restarts while the app is online."""
    if app.extensions.get("messenger_retry_worker"):
        return
    app.extensions["messenger_retry_worker"] = True

    def worker():
        # Allow migrations and the Flask listener to finish initializing.
        time.sleep(5)
        with app.app_context():
            # A crash can leave a row in processing; it is safe to retry once
            # at startup because the event id and outbound send are tracked.
            conversation_service.reset_processing_messenger_events()
        while True:
            try:
                with app.app_context():
                    for event_id in conversation_service.pending_messenger_event_ids():
                        process_messenger_event(app, event_id)
            except Exception:
                LOGGER.exception("Messenger retry worker failed")
            time.sleep(5)

    threading.Thread(target=worker, name="messenger-retry", daemon=True).start()
