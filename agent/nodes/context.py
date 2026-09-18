from langchain_core.messages import AIMessage, HumanMessage
from agent.lang import detect_language
from app.extensions import db
from app.models import Conversation, Message
def _text(state):
    return next((m.content for m in reversed(state.get("messages", [])) if isinstance(m, HumanMessage)), "")
def load_context(state):
    return {"language": state.get("language") or detect_language(_text(state)), "retrieved": [], "catalog_results": [], "tool_results": [], "error": None}
def persist_turn(state):
    conversation_id = state.get("conversation_id")
    if conversation_id:
        for message in state.get("messages", [])[-2:]:
            if isinstance(message, (HumanMessage, AIMessage)): db.session.add(Message(conversation_id=conversation_id, role="user" if isinstance(message, HumanMessage) else "assistant", content=message.content, meta={"intent": (state.get("plan") or {}).get("intent"), "doc_ids": [x["metadata"]["doc_id"] for x in state.get("retrieved", [])]}))
        db.session.commit()
    return {}
