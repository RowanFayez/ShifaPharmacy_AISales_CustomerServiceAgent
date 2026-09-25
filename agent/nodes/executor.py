import re
from langchain_core.messages import HumanMessage
from agent.tools import TOOL_REGISTRY
from agent.lang import normalize_for_retrieval
from app.services.kb_service import get_index
from app.extensions import db
from app.models import Product
def _text(state): return next((m.content for m in reversed(state.get("messages", [])) if isinstance(m, HumanMessage)), "")


def _is_generic_otc_category_request(text: str) -> bool:
    lowered = normalize_for_retrieval(text)
    return any(term in lowered for term in ("cold", "flu", "برد", "انفلونزا"))


def _is_category_list_request(text: str) -> bool:
    lowered = normalize_for_retrieval(text)
    return any(term in lowered for term in (
        "what categories", "which categories", "show categories", "what do you sell",
        "الفئات", "فئات", "كاتيجوري", "كاتيجوريز", "اقسام", "الأقسام",
    ))


def _is_delivery_question(text: str) -> bool:
    lowered = normalize_for_retrieval(text)
    return any(term in lowered for term in (
        "delivery", "delivery fee", "delivery time", "رسوم التوصيل", "وقت التوصيل", "موعد التوصيل", "توصيل",
    ))


def executor_catalog(state):
    plan = state["plan"]; terms = plan.get("product_mentions") or [_text(state)]
    query = " ".join(terms)
    if _is_category_list_request(query):
        results = TOOL_REGISTRY["list_categories"]({})
        results["name"] = "list_categories"
        return {"catalog_results": [], "tool_results": [results]}
    symptom_category = state.get("symptom_category")
    results = TOOL_REGISTRY["search_products"]({
        "query": "" if symptom_category else query,
        "category": symptom_category,
        "otc_only": bool(symptom_category) or _is_generic_otc_category_request(query),
        "lang": state.get("language", "en"),
    })
    results["name"] = "search_products"
    products = results.get("data") or []
    offered_product = next((product for product in products if not product.get("requires_prescription")), None)
    return {
        "catalog_results": products, "tool_results": [results],
        "last_catalog_product": offered_product, "last_catalog_results": products,
    }


def executor_product_info(state):
    """Answer a follow-up such as 'what does the third one do?' from the last list."""
    text = _text(state).casefold()
    ordinal_patterns = (
        (0, ("first", "الأول", "الاول", "اول", "1")),
        (1, ("second", "ثاني", "التاني", "الثاني", "2")),
        (2, ("third", "ثالث", "التالت", "الثالث", "3")),
        (3, ("fourth", "رابع", "الرابع", "4")),
    )
    index = next((i for i, words in ordinal_patterns if any(word in text for word in words)), None)
    products = state.get("last_catalog_results") or []
    if index is None or index >= len(products):
        return {"response": "ممكن تقول رقم المنتج أو اسمه عشان أوضح استخدامه؟" if state.get("language") in {"ar", "masri"} else "Which product number or name would you like me to explain?"}
    item = products[index]
    # The catalog result is deliberately enriched with the short description;
    # fall back to a live lookup for rows created before that field was added.
    if not item.get("short_description") and item.get("id"):
        product = db.session.get(Product, item["id"])
        if product:
            item = {**item, "short_description": product.short_description, "generic_name": product.generic_name}
    return {"product_focus": item}
def executor_rag(state):
    try:
        text = _text(state)
        retrieved = get_index().retrieve(
            text,
            metadata_filter={"category": "delivery"} if _is_delivery_question(text) else None,
        )
    except Exception:
        return {"retrieved": [], "tool_results": state.get("tool_results", []), "error": "RAG_UNAVAILABLE"}
    return {"retrieved": retrieved, "tool_results": state.get("tool_results", [])}
def executor_tools(state):
    pending = state.get("pending_action") or {}; result = TOOL_REGISTRY["create_order"](pending)
    result["name"] = "create_order"
    return {"tool_results": state.get("tool_results", []) + [result], "pending_action": None if result["ok"] else pending,
            "order_stage": None if result["ok"] else state.get("order_stage"), "order_draft": None if result["ok"] else state.get("order_draft")}

def executor_order_status(state):
    match = re.search(r"\b(SHF-[A-Z0-9-]+)\b", _text(state), re.I)
    if not match or not state.get("customer_ref"):
        return {"tool_results": state.get("tool_results", []), "error": "ORDER_STATUS_NEEDS_ORDER_NUMBER_AND_PHONE"}
    result = TOOL_REGISTRY["get_order_status"]({"order_number": match.group(1).upper(), "phone": state["customer_ref"]})
    result["name"] = "get_order_status"
    return {"tool_results": state.get("tool_results", []) + [result]}

def escalation_exec(state):
    if not state.get("conversation_id"):
        return {"needs_human": True}
    result = TOOL_REGISTRY["escalate_to_pharmacist"]({"conversation_id": state["conversation_id"], "question": _text(state)})
    result["name"] = "escalate_to_pharmacist"
    return {"tool_results": state.get("tool_results", []) + [result], "needs_human": True}
