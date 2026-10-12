"""Deterministic gates that cannot be bypassed by an LLM prompt."""
from agent.prompts import ar, en, masri
from agent.tools import TOOL_REGISTRY
from app.services import order_service

def _prompt(language): return {"ar": ar, "masri": masri}.get(language, en)


def _review_summary(draft, details, quote, language):
    product = draft.get("name_ar") or draft["name"] if language in {"ar", "masri"} else draft["name"]
    quantity = draft.get("quantity", 1)
    if language == "en":
        return (
            "Please review your order before I create it:\n"
            f"- {quantity} x {product}\n- Name: {details['name']}\n- Phone: {details['phone']}\n"
            f"- Address: {details['address']}\n- Total: EGP {quote['total']} (including EGP {quote['delivery_fee']} delivery)\n"
            "Reply \"confirm\" to place the order."
        )
    return (
        "تمام، راجع الطلب قبل الإنشاء:\n"
        f"- {quantity} × {product}\n- الاسم: {details['name']}\n- رقم الموبايل: {details['phone']}\n"
        f"- العنوان: {details['address']}\n- الإجمالي: {quote['total']} جنيه (شامل {quote['delivery_fee']} جنيه توصيل)\n"
        "اكتب «تمام» لتأكيد الطلب."
    )

def rx_gate(state):
    matched = next((item for item in state.get("catalog_results", []) if item.get("requires_prescription")), None)
    if not matched: return {"safety_flag": None}
    results = state.get("tool_results", [])
    if state.get("customer_ref"):
        request = TOOL_REGISTRY["request_prescription_upload"]({"customer_ref": state["customer_ref"], "product_id": matched["id"], "note": "Requested through customer chat."})
        request["name"] = "request_prescription_upload"; results = results + [request]
    return {"safety_flag": "rx_required", "tool_results": results}

def confirmation_gate(state):
    if state.get("pending_action"): return {}
    plan = state.get("plan") or {}
    product = next((item for item in state.get("catalog_results", []) if not item.get("requires_prescription")), None)
    # A shopper may say "I want to order it" after a previous catalogue
    # response.  Reuse that live product rather than trying to search the
    # pronoun-filled follow-up as though it were a product name.
    if product is None:
        offered = state.get("last_catalog_product")
        if offered and not offered.get("requires_prescription"):
            product = offered
    if product is None:
        return {"response": "I could not find an orderable product."}
    quantity = plan.get("quantities", {}).get(product["name"], 1)
    items = [{"product_id": product["id"], "quantity": quantity}]
    if not state.get("customer_ref"):
        return {
            "pending_action": None,
            "order_stage": "collect_details",
            "order_draft": {"id": product["id"], "name": product["name"], "name_ar": product.get("name_ar"), "quantity": quantity},
        }
    draft = {"id": product["id"], "name": product["name"], "name_ar": product.get("name_ar"), "quantity": quantity}
    details = {
        "name": state.get("customer_name") or "",
        "phone": state.get("customer_ref") or "",
        "address": state.get("customer_address") or "",
    }
    try:
        quote = order_service.quote_order(items)
        review = _review_summary(draft, details, quote, state.get("language") or "en")
    except order_service.ServiceError:
        return {"response": "This product is no longer available to order." if state.get("language") == "en" else "هذا المنتج لم يعد متاحًا للطلب الآن."}
    return {
        "pending_action": {"customer_ref": state.get("customer_ref") or "", "items": items, "address": state.get("customer_address") or ""},
        "order_stage": "awaiting_confirmation",
        "order_draft": draft,
        "order_contact_details": details,
        "response": review,
    }

def safety_handler(state):
    results = state.get("tool_results", [])
    if state.get("conversation_id"):
        handoff = TOOL_REGISTRY["escalate_to_pharmacist"]({"conversation_id": state["conversation_id"], "question": "Customer asked for medical advice."})
        handoff["name"] = "escalate_to_pharmacist"; results = results + [handoff]
    text = _prompt(state.get("language")).SAFETY
    from agent.lang import normalize_for_retrieval
    current = normalize_for_retrieval(next((m.content for m in reversed(state.get("messages", [])) if hasattr(m, "content")), ""))
    if any(term in current for term in ("anemia", "iron deficiency", "أنيميا", "فقر دم")):
        text = (
            "الأنيميا لها أسباب مختلفة، ومينفعش أختار مكمل أو جرعة من غير تقييم وتحاليل. أقدر أعرض قسم الفيتامينات كمعلومات عامة، أو أوصلك بالصيدلي."
            if state.get("language") in {"ar", "masri"} else
            "Anemia can have different causes, so I cannot choose a supplement or dose without proper assessment. I can show the vitamins category as general information or connect you with a pharmacist."
        )
    return {"response": text, "needs_human": True, "tool_results": results}
