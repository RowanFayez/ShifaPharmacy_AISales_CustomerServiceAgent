"""Plan production with deterministic fast paths and a cached structured LLM fallback."""
import os
import re
from langchain_core.messages import HumanMessage
from agent.cache import ReasonerCache
from agent.lang import normalize_for_retrieval
from agent.llm import get_chat_model
from agent.schemas import Plan
from agent.nodes.context import _is_confirmation

def _message(state): return next((m.content.strip() for m in reversed(state.get("messages", [])) if isinstance(m, HumanMessage)), "")


def _is_catalog_question(text: str) -> bool:
    """Keep common shopping questions on the live SQL catalog path.

    This deliberately happens before the LLM: product availability and price must
    never be answered from the policy knowledge base or from model memory.
    """
    lowered = normalize_for_retrieval(text)
    product_cues = (
        "panadol", "advil", "brufen", "augmentin", "vitamin", "cold", "flu",
        "medicine", "medicines", "available", "in stock", "price", "how much",
        "category", "categories", "vitamins", "supplements", "baby", "personal care", "diabetes", "device",
        "skin", "skin care", "skincare", "cream", "moisturizer", "بانادول", "بنادول", "كريم", "بشرة", "بشره", "جلد",
        "باناد", "ادفيل", "بروفين", "اوجمنتين", "فيتامين", "دواء", "دوا", "ادوية", "ادويه",
        "البرد", "انفلونزا", "متوفر", "موجود", "بكام", "سعر", "فئات", "كاتيجوري", "اقسام",
        "طفل", "اطفال", "عناية", "سكري", "سكر", "السكر", "اجهزة", "مسكنات",
    )
    delivery_only_cues = (
        "delivery", "shipping", "delivery fee", "delivery time", "رسوم التوصيل",
        "موعد التوصيل", "خدمة التوصيل", "خدمة توصيل", "التوصيل", "توصيل", "شحن",
        "دليفري", "ديليفري", "الدليفري", "الديليفري", "الشحن",
    )
    # An availability question beginning with "في" often contains a brand that
    # is not yet in our aliases.  Keep it on the local catalog path instead of
    # waiting for an external LLM before saying it is not stocked.
    generic_availability = lowered.startswith(("في ", "هل يوجد", "عندكم", "عندكو", "do you have", "is there"))
    return (any(cue in lowered for cue in product_cues) or generic_availability) and not any(cue in lowered for cue in delivery_only_cues)


def _wants_to_order(text: str) -> bool:
    lowered = normalize_for_retrieval(text)
    return any(cue in lowered for cue in (
        "i want", "i'd like", "buy", "order", "add to cart", "add it",
        "عايز", "عاوز", "عايزة", "هاخد", "حابب اطلب", "اطلب", "اطلبي", "ضيف", "أضف",
    ))

def _is_service_question(text: str) -> bool:
    lowered = normalize_for_retrieval(text)
    return any(cue in lowered for cue in (
        "delivery", "delivery fee", "delivery time", "branch", "branches", "hours", "payment",
        "توصيل", "دليفري", "ديليفري", "الشحن", "رسوم", "موعد", "فروع", "فرع", "مواعيد", "ساعات العمل", "دفع",
    ))


def _is_catalog_follow_up(text: str) -> bool:
    """Recognise a natural follow-up asking for variants after a product list."""
    lowered = normalize_for_retrieval(text)
    return any(cue in lowered for cue in (
        "which one", "which ones", "which type", "what types", "other types",
        "أي نوع", "اي نوع", "أنواع", "انواع", "النوع", "الأنواع", "الانواع",
        "اللي عندك", "الموجود عندك", "منه",
    ))

def _is_greeting(text: str) -> bool:
    lowered = normalize_for_retrieval(text).strip()
    return lowered in {"hello", "hi", "hey", "السلام عليكم", "اهلا", "أهلا", "اهلاً", "أهلاً", "ازيك", "إزيك"}

def _is_thanks(text: str) -> bool:
    lowered = normalize_for_retrieval(text).strip()
    return lowered in {"thanks", "thank you", "شكرا", "شكرًا", "متشكر", "تسلم"}

def _is_acknowledgement(text: str) -> bool:
    lowered = normalize_for_retrieval(text).strip()
    return lowered in {"تمام", "ماشي", "حاضر", "اوكي", "أوكي", "okay", "ok"}


def _is_conversational_opener(text: str) -> bool:
    """Short attention-getters should not be sent to an unconstrained reply."""
    lowered = normalize_for_retrieval(text).strip(" ؟?!.,")
    return lowered in {
        "طيب", "طيب بقولك", "بقولك", "بقولك حاجة", "لو سمحت", "معلش", "اسمعني",
        "اتفضل", "hello", "hi", "excuse me", "can i ask", "i have a question",
    }


def _has_product_ordinal_question(text: str) -> bool:
    lowered = normalize_for_retrieval(text)
    ordinal = ("first", "second", "third", "fourth", "الأول", "الاول", "التاني", "الثاني", "التالت", "الثالث", "الرابع")
    follow_up = ("what", "use", "does", "بيعمل", "استخدام", "فايد", "يعالج")
    return any(word in lowered for word in ordinal) and any(word in lowered for word in follow_up)

def reasoner(state):
    text, language = _message(state), state.get("language") or "en"
    if not text: plan = Plan(intent="chitchat", language=language, rationale="empty message")
    elif _is_greeting(text): plan = Plan(intent="chitchat", language=language, rationale="greeting")
    elif _is_thanks(text) or (
        _is_acknowledgement(text)
        and not state.get("pending_action")
        and state.get("order_stage") not in {"collect_details", "awaiting_confirmation"}
    ): plan = Plan(intent="chitchat", language=language, rationale="thanks")
    elif _is_conversational_opener(text):
        plan = Plan(intent="chitchat", language=language, rationale="conversation opener")
    elif state.get("symptom_tier") == "tier1":
        plan = Plan(
            intent="sales", language=language, needs_catalog_lookup=True,
            product_mentions=[], wants_to_order=False, rationale="general OTC suggestion",
        )
    elif state.get("offer_accepted"):
        plan = Plan(intent="order_action", language=language, wants_to_order=True, rationale="accepted previously offered product")
    elif state.get("pending_action") and _is_confirmation(text):
        plan = Plan(intent="order_action", language=language, confirming_previous_action=True, wants_to_order=True, rationale="confirmed pending order")
    elif re.search(r"\bSHF-[A-Z0-9-]+\b", text, re.I): plan = Plan(intent="order_status", language=language, rationale="order number")
    elif _has_product_ordinal_question(text) and state.get("last_catalog_results"):
        plan = Plan(intent="customer_service", language=language, rationale="product info follow-up")
    elif any(word in text.casefold() for word in ("diagnose", "dosage", "جرعة", "تشخيص")):
        plan = Plan(intent="safety", language=language, is_medical_question=True, rationale="medical request")
    elif _is_catalog_question(text):
        wants_to_order = _wants_to_order(text)
        plan = Plan(intent="sales", language=language, needs_catalog_lookup=True, product_mentions=[text], wants_to_order=wants_to_order, rationale="catalog availability or price question")
    elif _is_service_question(text):
        plan = Plan(intent="customer_service", language=language, needs_rag=True, rationale="delivery, branch, or payment question")
    elif _wants_to_order(text):
        plan = Plan(intent="sales", language=language, wants_to_order=True, rationale="order intent without product")
    else:
        material = f"{text.casefold()}|{language}|{bool(state.get('pending_action'))}|{(state.get('plan') or {}).get('intent')}"
        cache = ReasonerCache()
        cached = cache.get(material)
        if cached: plan = Plan.model_validate(cached)
        else:
            history = "\n".join(
                f"{getattr(message, 'type', 'message')}: {getattr(message, 'content', '')}"
                for message in state.get("messages", [])[-6:]
            )
            prompt = (
                "Classify this pharmacy customer message and return only the Plan schema. "
                "Allowed intents: chitchat, customer_service, sales, order_action, order_status, safety, escalation. "
                "Use customer_service for delivery, branches, hours, payment, returns, or general product questions. "
                "Use order_status only when the customer provides an order number like SHF-123. "
                "Use sales for product availability, prices, categories, alternatives, or a request to buy. "
                "Use safety for diagnosis, dosage, interactions, red flags, or personal medical treatment. "
                f"The detected language is {language}. Current message: {text}\nConversation context:\n{history}"
            )
            try: plan = get_chat_model().with_structured_output(Plan).invoke([HumanMessage(content=prompt)])
            except Exception:
                fallback = os.getenv("LLM_FALLBACK_MODEL")
                try: plan = get_chat_model(fallback).with_structured_output(Plan).invoke([HumanMessage(content=prompt)]) if fallback else None
                except Exception: plan = None
            if plan is None: return {"plan": Plan(intent="customer_service", language=language, needs_rag=True, rationale="LLM unavailable").model_dump(), "language": language, "error": "LLM_UNAVAILABLE", "llm_intent_used": False, "llm_error": "LLM_UNAVAILABLE"}
            # The model is advisory.  Correct known high-risk ambiguities
            # before routing so a delivery question cannot become order status.
            if _is_service_question(text) and not re.search(r"\bSHF-[A-Z0-9-]+\b", text, re.I):
                plan = plan.model_copy(update={"intent": "customer_service", "needs_rag": True, "needs_catalog_lookup": False})
            elif _is_catalog_follow_up(text) and state.get("last_catalog_results"):
                plan = plan.model_copy(update={"intent": "sales", "needs_catalog_lookup": True, "product_mentions": [text]})
            cache.set(material, plan.model_dump())
            return {"plan": plan.model_dump(), "language": plan.language, "llm_intent_used": True}
    return {"plan": plan.model_dump(), "language": plan.language, "llm_used": False}
