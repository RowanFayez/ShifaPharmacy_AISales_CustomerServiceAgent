from langchain_core.messages import HumanMessage
from agent.llm import get_chat_model
from agent.schemas import Plan
def reasoner(state):
    text = next((m.content.strip() for m in reversed(state.get("messages", [])) if isinstance(m, HumanMessage)), "")
    language = state.get("language") or "en"
    if not text: plan = Plan(intent="chitchat", language=language, rationale="empty message")
    elif state.get("pending_action") and text.casefold() in {"yes", "y", "confirm", "ايوه", "اه", "تمام"}: plan = Plan(intent="order_action", language=language, confirming_previous_action=True, wants_to_order=True, rationale="confirmed pending order")
    elif any(word in text.casefold() for word in ("diagnose", "dosage", "جرعة", "تشخيص")): plan = Plan(intent="safety", language=language, is_medical_question=True, rationale="medical request")
    else:
        plan = get_chat_model().with_structured_output(Plan).invoke([HumanMessage(content=f"Classify this pharmacy customer message. language={language}. Message: {text}")])
    return {"plan": plan.model_dump(), "language": plan.language}
