from langchain_core.messages import AIMessage, HumanMessage
from agent.lang import detect_language, normalize_for_retrieval
from app.services import conversation_service
def _text(state):
    return next((m.content for m in reversed(state.get("messages", [])) if isinstance(m, HumanMessage)), "")


def _is_confirmation(text):
    return text.strip().casefold() in {"yes", "y", "confirm", "ok", "ايوه", "اه", "تمام"}


def _accepts_catalog_offer(text):
    normalized = normalize_for_retrieval(text)
    phrases = {
        "i want it", "i'll take it", "i will take it", "add it", "buy it",
        "عايزاه", "عايزه", "عايزه اطلبه", "عايزه أطلبه", "عايزه اعمل اوردر", "عايزه أعمل اوردر",
        "عايز اعمل اوردر", "عاوز اعمل اوردر", "هاخده", "هاخدها", "خده", "خدي",
    }
    normalized_phrases = {normalize_for_retrieval(phrase) for phrase in phrases}
    return normalized in normalized_phrases or any(
        phrase in normalized for phrase in normalized_phrases if len(phrase) > 3
    )


def load_context(state):
    context = conversation_service.customer_context(state.get("customer_id"))
    # These values describe one turn only.  The checkpointer keeps state for
    # order confirmation, but a prior reply or safety flag must never leak into
    # the next customer message.
    # A new question replaces an unconfirmed cart.  Only an explicit "yes"
    # keeps the pending action for the confirmation path.
    text = _text(state)
    offered_product = state.get("last_catalog_product")
    previous_catalog_results = state.get("last_catalog_results") or []
    offer_accepted = bool(offered_product and _accepts_catalog_offer(text))
    previous_stage = state.get("order_stage")
    if offer_accepted:
        pending_action, order_stage = None, "collect_details"
        order_draft = {key: offered_product.get(key) for key in ("id", "name", "name_ar")}
        order_draft["quantity"] = 1
        order_contact_details = {}
    elif previous_stage == "collect_details":
        pending_action, order_stage, order_draft = None, "collect_details", state.get("order_draft")
        order_contact_details = state.get("order_contact_details") or {}
    elif _is_confirmation(text) and state.get("pending_action"):
        pending_action, order_stage, order_draft = state.get("pending_action"), "awaiting_confirmation", state.get("order_draft")
        order_contact_details = state.get("order_contact_details") or {}
    else:
        pending_action, order_stage, order_draft, order_contact_details = None, None, None, {}
    return {
        "language": detect_language(_text(state)), "retrieved": [], "catalog_results": [],
        "tool_results": [], "error": None, "response": None, "safety_flag": None,
        "needs_human": False, "pending_action": pending_action, "symptom_tier": None,
        "symptom_category": None, "last_catalog_product": offered_product,
        "last_catalog_results": previous_catalog_results, "product_focus": None,
        "is_first_turn": bool(state.get("is_first_turn")), "channel": state.get("channel"),
        "offer_accepted": offer_accepted, "order_stage": order_stage, "order_draft": order_draft,
        "order_contact_details": order_contact_details,
        "order_details_handled": False, **context,
    }
def persist_turn(state):
    conversation_id = state.get("conversation_id")
    if conversation_id:
        messages = [{"role": "user" if isinstance(message, HumanMessage) else "assistant", "content": message.content}
                    for message in state.get("messages", [])[-2:] if isinstance(message, (HumanMessage, AIMessage))]
        conversation_service.persist_messages(conversation_id, messages, {"intent": (state.get("plan") or {}).get("intent"), "language": state.get("language"), "tools_called": [x.get("name") for x in state.get("tool_results", [])], "doc_ids": [x["metadata"]["doc_id"] for x in state.get("retrieved", [])], "scores": [x["score"] for x in state.get("retrieved", [])]})
    return {}
