"""Deterministic chat-checkout details collection; no model is used here."""
from __future__ import annotations

import re
from decimal import Decimal

from langchain_core.messages import HumanMessage

from app.services import conversation_service, order_service


_PHONE = re.compile(r"(?<!\d)(?:\+20|0020|0)1[0125]\d{8}(?!\d)")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _text(state: dict) -> str:
    return next(
        (message.content.strip() for message in reversed(state.get("messages", [])) if isinstance(message, HumanMessage)),
        "",
    )


def _normalise_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value.translate(_ARABIC_DIGITS))
    if digits.startswith("0020"):
        digits = digits[2:]
    if digits.startswith("20"):
        digits = "0" + digits[2:]
    return digits


def _label_value(text: str, labels: tuple[str, ...]) -> str | None:
    labels_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:^|[\n،,;])\s*(?:{labels_pattern})\s*(?:[:：=-]\s*)?([^\n،,;]+)",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _clean_fragment(value: str) -> str:
    cleaned = value.strip(" \t\n،,;:-")
    cleaned = re.sub(
        r"^(?:الاسم|اسم المستلم|اسم العميل|اسمي|name|العنوان|مكان التوصيل|address)\s*[:：=-]?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def _parse_details(text: str) -> dict[str, str | None]:
    normalised = text.translate(_ARABIC_DIGITS)
    phone_match = _PHONE.search(normalised)
    phone = _normalise_phone(phone_match.group(0)) if phone_match else None
    name = _label_value(normalised, ("الاسم", "اسم المستلم", "اسم العميل", "اسمي", "name"))
    address = _label_value(normalised, ("العنوان", "مكان التوصيل", "address"))

    # A natural one-line reply is also accepted: "روان فايز 010... الحديد والصلب".
    if phone_match:
        before, after = normalised[:phone_match.start()], normalised[phone_match.end():]
        if not name:
            # Accept conversational forms such as "أنا سما فايز، رقمي ...".
            before = re.split(
                r"(?:الموبايل|رقم(?:ي| التليفون)?|تليفوني|phone|mobile)\s*[:：=-]?",
                before,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            name = _clean_fragment(re.sub(r"^(?:أنا|انا|i am|i'm)\s+", "", before, flags=re.IGNORECASE))
        if not address:
            # Accept "ساكنة في ..." / "عايش في ..." after the number.
            address = _clean_fragment(
                re.sub(
                    r"^(?:العنوان|مكان التوصيل|ساكن(?:ة|ه)?\s+في|عايش(?:ة|ه)?\s+في|ساكن(?:ة|ه)?|عايش(?:ة|ه)?|في|address|living in)\s*(?:[:：=-]\s*)?",
                    "",
                    after.strip(" \t\n،,;:-"),
                    flags=re.IGNORECASE,
                )
            )
    name = _clean_fragment(name) if name else None
    address = _clean_fragment(address) if address else None
    return {"name": name if name and len(name) >= 2 else None, "phone": phone, "address": address if address and len(address) >= 3 else None}


def _details_prompt(language: str) -> str:
    if language == "en":
        return (
            "To prepare the order, send the recipient's name, mobile number, and delivery address in one message.\n"
            "Example: Name: Rowan Fayez, phone: 01012345678, address: Hadid w Solb.\n"
            "The order will not be created and stock will not change until you confirm the summary."
        )
    return (
        "تمام، علشان أجهز الطلب ابعت اسم المستلم ورقم الموبايل والعنوان في رسالة واحدة.\n"
        "مثال: الاسم: روان فايز، الموبايل: 01012345678، العنوان: الحديد والصلب.\n"
        "مش هيتعمل طلب ولا هيتخصم من المخزون قبل ما تأكد الملخص النهائي."
    )


def _missing_details_prompt(details: dict[str, str | None], language: str) -> str:
    missing = []
    labels = {"name": "الاسم", "phone": "رقم موبايل مصري صحيح", "address": "العنوان"}
    for key in ("name", "phone", "address"):
        if not details.get(key):
            missing.append(labels[key])
    if language == "en":
        return "I still need: " + ", ".join({"الاسم": "name", "رقم موبايل مصري صحيح": "a valid Egyptian mobile number", "العنوان": "delivery address"}[item] for item in missing) + "."
    return "لسه محتاج: " + "، ".join(missing) + "."


def _product_name(draft: dict, language: str) -> str:
    return draft.get("name_ar") or draft["name"] if language in {"ar", "masri"} else draft["name"]


def _quote_summary(draft: dict, details: dict[str, str], quote: dict, language: str) -> str:
    quantity = draft.get("quantity", 1)
    product = _product_name(draft, language)
    if language == "en":
        return (
            "Please review your order before I create it:\n"
            f"- {quantity} × {product}\n"
            f"- Name: {details['name']}\n- Phone: {details['phone']}\n- Address: {details['address']}\n"
            f"- Total: EGP {quote['total']} (including EGP {quote['delivery_fee']} delivery)\n"
            "Reply “confirm” to place the order."
        )
    return (
        "تمام، راجع الطلب قبل الإنشاء:\n"
        f"- {quantity} × {product}\n"
        f"- الاسم: {details['name']}\n- رقم الموبايل: {details['phone']}\n- العنوان: {details['address']}\n"
        f"- الإجمالي: {quote['total']} جنيه (شامل {quote['delivery_fee']} جنيه توصيل)\n"
        "اكتب «تمام» لتأكيد الطلب."
    )


def order_details(state):
    """Collect checkout data and produce a confirmation-ready pending action."""
    stage = state.get("order_stage")
    language = state.get("language") or "en"
    if stage != "collect_details":
        return {"order_details_handled": False}
    if state.get("offer_accepted"):
        return {"response": _details_prompt(language), "order_details_handled": True}

    draft = state.get("order_draft") or {}
    if not draft:
        return {"response": _details_prompt(language), "order_details_handled": True}
    parsed = _parse_details(_text(state))
    previous = state.get("order_contact_details") or {}
    # Keep valid fields from an earlier Messenger turn when the customer sends
    # a correction or splits the checkout data across several messages.
    details = {key: parsed.get(key) or previous.get(key) for key in ("name", "phone", "address")}
    if not all(details.values()):
        return {
            "response": _missing_details_prompt(details, language) + "\n" + _details_prompt(language),
            "order_contact_details": details,
            "order_details_handled": True,
        }

    customer = conversation_service.upsert_chat_customer(
        str(details["name"]), str(details["phone"]), str(details["address"]), state.get("customer_id")
    )
    conversation_service.attach_customer(state.get("conversation_id"), customer.id)
    items = [{"product_id": draft["id"], "quantity": draft.get("quantity", 1)}]
    try:
        quote = order_service.quote_order(items)
    except order_service.ServiceError:
        return {"response": "هذا المنتج لم يعد متاحًا للطلب الآن." if language != "en" else "This product is no longer available to order.", "order_details_handled": True, "order_stage": None, "order_draft": None}
    pending_action = {"customer_ref": customer.phone, "items": items, "address": str(details["address"])}
    return {
        "customer_id": customer.id,
        "customer_ref": customer.phone,
        "customer_address": str(details["address"]),
        "pending_action": pending_action,
        "order_stage": "awaiting_confirmation",
        "order_draft": draft,
        "order_contact_details": details,
        "response": _quote_summary(draft, details, quote, language),
        "order_details_handled": True,
    }
