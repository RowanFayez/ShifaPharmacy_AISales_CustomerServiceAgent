"""Checkout detail extraction and the review-before-create boundary.

The parser accepts natural, unordered Messenger text first.  A structured
model is only an extraction fallback for prose the local parser cannot split;
it may never create an order or override the transactional gates.
"""
from __future__ import annotations

import re

from flask import current_app, has_app_context
from langchain_core.messages import HumanMessage

from app.services import conversation_service, order_service
from agent.llm import get_chat_model
from agent.schemas import CheckoutDetails


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
        r"^(?:الاسم|اسم المستلم|اسم العميل|اسم|اسمي|name|recipient|"
        r"العنوان|عنواني|مكان التوصيل|address|phone|mobile|الموبايل|رقمي)\s*[:：=-]?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


_FIELD_MARKERS = (
    ("name", ("اسم المستلم", "اسم العميل", "الاسم", "recipient name", "recipient", "اسمي", "اسم", "name")),
    ("phone", ("رقم الموبايل", "رقم التليفون", "الموبايل", "الموبيل", "ورقمي", "والموبايل", "ورقم الموبايل", "رقمي", "تليفوني", "my phone", "my mobile", "phone", "mobile")),
    ("address", ("مكان التوصيل", "عنوان التوصيل", "العنوان", "عنواني", "address", "living in", "live in")),
)


def _marked_fragments(text: str) -> dict[str, str]:
    """Split fields by labels, regardless of their order or punctuation."""
    alternatives = []
    for field, labels in _FIELD_MARKERS:
        # Longer labels must win over the plain ``اسم`` marker.
        for label in sorted(labels, key=len, reverse=True):
            alternatives.append((field, label))
    alternatives.sort(key=lambda item: len(item[1]), reverse=True)
    pattern = "|".join(re.escape(label) for _, label in alternatives)
    matches = list(re.finditer(rf"(?<!\w)(?:{pattern})(?!\w)\s*[:：=-]?", text, re.IGNORECASE))
    fields: dict[str, str] = {}
    for index, match in enumerate(matches):
        label = match.group(0).strip().rstrip(":：=-").casefold()
        field = next((field for field, labels in _FIELD_MARKERS if label in {item.casefold() for item in labels}), None)
        if not field:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = text[match.end():end].strip(" \t\n،,;:-")
        if value:
            # Keep the latest explicit occurrence: customers often say
            # "the address is wrong, the address is ..." while correcting a
            # review.  A later field is the customer's intended value.
            fields[field] = value
    return fields


def _parse_details(text: str) -> dict[str, str | None]:
    normalised = text.translate(_ARABIC_DIGITS)
    phone_match = _PHONE.search(normalised)
    phone = _normalise_phone(phone_match.group(0)) if phone_match else None
    marked = _marked_fragments(normalised)
    name = marked.get("name")
    address = marked.get("address")
    if address:
        address = re.sub(r"\s+(?:and\s+my|و(?:رقمي|الموبايل)).*$", "", address, flags=re.IGNORECASE)
        address = re.sub(r"\s+and\s*$", "", address, flags=re.IGNORECASE)

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
        # The address may precede the number too: "I am ..., I live in ...,
        # my mobile is ...". Split the location cue before treating the
        # whole sentence as a name.  This runs even when a location marker
        # already supplied an address fragment.
        location = re.search(
            r"(?:ساكن(?:ة|ه)?\s+في|عايش(?:ة|ه)?\s+في|living\s+in|live\s+in|from)\s+(.+)$",
            before,
            flags=re.IGNORECASE,
        )
        if location:
            if not address:
                address = _clean_fragment(re.sub(r"\s+(?:and\s+my|و(?:رقمي|الموبايل)).*$", "", location.group(1), flags=re.IGNORECASE))
                address = re.sub(r"\s+and\s*$", "", address, flags=re.IGNORECASE)
            name_part = before[: location.start()]
            name = _clean_fragment(re.sub(r"(?:,|،)?\s*(?:أنا|انا|i am|i'm|i)\s*$", "", name_part, flags=re.IGNORECASE))
            name = _clean_fragment(re.sub(r"^(?:أنا|انا|i am|i'm)\s+", "", name, flags=re.IGNORECASE))
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
    # A phone marker may have captured the number plus a connector.  Always
    # trust the validated number found by the Egyptian mobile pattern instead.
    return {"name": name if name and len(name) >= 2 else None, "phone": phone, "address": address if address and len(address) >= 3 else None}


def _llm_details(text: str, previous: dict[str, str | None]) -> dict[str, str | None]:
    """Extract explicit fields from difficult prose without inventing values."""
    if not has_app_context() or (current_app.testing and not current_app.config.get("LLM_CHECKOUT_IN_TESTS", False)):
        return {}
    prompt = (
        "Extract checkout contact details from the customer's latest message. "
        "Return only the CheckoutDetails schema. Never infer, normalize a name, "
        "or invent a missing field; use null when the customer did not explicitly "
        "provide it. Keep the address text as written. Normalize an Egyptian phone "
        "to 11 digits only when it is explicitly present. This is extraction only; "
        "do not confirm or create an order.\n"
        f"Previous fields (may be corrected): {previous}\nLatest message: {text}"
    )
    for model_name in (None, __import__("os").getenv("LLM_FALLBACK_MODEL")):
        if model_name is None and not __import__("os").getenv("OPENROUTER_API_KEY"):
            continue
        try:
            result = get_chat_model(model_name).with_structured_output(CheckoutDetails).invoke([HumanMessage(content=prompt)])
            data = result.model_dump() if isinstance(result, CheckoutDetails) else CheckoutDetails.model_validate(result).model_dump()
            extracted = {"name": None, "phone": None, "address": None}
            if data.get("name"):
                value = _clean_fragment(str(data["name"]))
                extracted["name"] = value if len(value) >= 2 else None
            if data.get("address"):
                value = _clean_fragment(str(data["address"]))
                extracted["address"] = value if len(value) >= 3 else None
            if data.get("phone"):
                phone = _normalise_phone(str(data["phone"]))
                if _PHONE.fullmatch(phone):
                    extracted["phone"] = phone
            if any(extracted.values()) or model_name == __import__("os").getenv("LLM_FALLBACK_MODEL"):
                return extracted
        except Exception:
            continue
    return {}


def _looks_like_checkout_message(text: str) -> bool:
    """Return whether a turn is plausibly supplying checkout contact data.

    Checkout is a stateful branch, but it must not swallow a new product or
    service question.  A phone number or an explicit contact/address label is
    a much safer signal than treating every following message as checkout
    data.
    """
    normalized = text.translate(_ARABIC_DIGITS)
    if _PHONE.search(normalized):
        return True
    return bool(re.search(
        r"(?:الاسم|اسم\s+(?:المستلم|العميل)?|اسمي|الموبايل|رقم(?:ي| التليفون)?|تليفوني|"
        r"العنوان|مكان\s+التوصيل|ساكن(?:ة|ه)?|عايش(?:ة|ه)?|name|phone|mobile|address|living\s+in)",
        normalized,
        flags=re.IGNORECASE,
    ))


def _is_short_checkout_ack(text: str) -> bool:
    return text.strip().casefold() in {
        "yes", "y", "ok", "okay", "تمام", "اه", "أه", "ايوه", "أيوه", "ماشي", "حاضر",
    }


def _details_prompt(language: str) -> str:
    if language == "en":
        return (
            "To prepare the order, send the recipient's name, mobile number, and delivery address. "
            "You can write them naturally in any order; labels are optional.\n"
            "Example: I'm Rowan Fayez, my number is 01012345678, and I live in Hadid w Solb.\n"
            "The order will not be created and stock will not change until you confirm the summary."
        )
    return (
        "تمام، علشان أجهز الطلب ابعت اسم المستلم ورقم الموبايل والعنوان. اكتبهم بطريقتك وبأي ترتيب، ومش لازم تستخدم عناوين للبيانات.\n"
        "مثال: أنا روان فايز، رقمي 01012345678 وساكنة في الحديد والصلب.\n"
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
    incoming = _text(state)
    # A customer can change their mind or ask a fresh catalog/service question
    # while checkout is open.  Do not repeat the checkout prompt forever; clear
    # only the transient draft and let the normal reasoner handle that message.
    if not _looks_like_checkout_message(incoming) and not _is_short_checkout_ack(incoming):
        return {
            "order_details_handled": False,
            "order_stage": None,
            "order_draft": None,
            "order_contact_details": {},
        }
    parsed = _parse_details(incoming)
    previous = state.get("order_contact_details") or {}
    # A difficult free-form turn gets one structured extraction attempt.  The
    # model is advisory and only explicit, validated fields are merged below.
    if not all(parsed.values()):
        model_details = _llm_details(incoming, previous)
        parsed = {key: model_details.get(key) or parsed.get(key) for key in ("name", "phone", "address")}
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
