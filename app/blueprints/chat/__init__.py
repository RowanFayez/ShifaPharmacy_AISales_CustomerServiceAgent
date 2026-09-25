"""Customer-facing chat UI and JSON endpoint."""
from flask import Blueprint, current_app, jsonify, render_template, request, session
from langchain_core.messages import HumanMessage
from agent.graph import build_graph
from app.services import catalog_service, conversation_service
import uuid


chat_bp = Blueprint("chat", __name__)

@chat_bp.get("/chat")
def chat_page():
    return render_template("chat/index.html")


@chat_bp.get("/privacy-policy")
def privacy_policy():
    """Public privacy notice required by Meta before Messenger Live mode."""
    return render_template("privacy_policy.html")


@chat_bp.get("/data-deletion")
def data_deletion():
    """Public instructions for a person requesting deletion of chat data."""
    return render_template("data_deletion.html")


@chat_bp.get("/api/catalog/categories")
def catalog_categories():
    """Expose active storefront categories for the chat quick-action menu."""
    return jsonify({"ok": True, "categories": catalog_service.list_categories()})

@chat_bp.post("/api/chat")
def chat_api():
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("message", "")).strip()
    if not text or len(text) > 2000:
        return jsonify({"ok": False, "error": "Enter a message of up to 2,000 characters."}), 400
    thread_id = session.setdefault("chat_thread_id", str(uuid.uuid4()))
    conversation = conversation_service.get_or_create_web_conversation(thread_id)
    try:
        result = build_graph().invoke({"messages": [HumanMessage(content=text)], "conversation_id": conversation.id, "customer_id": conversation.customer_id}, config={"configurable": {"thread_id": thread_id}})
    except Exception:
        current_app.logger.exception("Chat turn failed for conversation %s", conversation.id)
        return jsonify({"ok": False, "error": "I’m unable to respond right now. Please try again or contact a pharmacist."}), 503
    return jsonify({"ok": True, "conversation_id": conversation.id, "reply": result.get("response", "I’m unable to respond right now."), "language": result.get("language")})
