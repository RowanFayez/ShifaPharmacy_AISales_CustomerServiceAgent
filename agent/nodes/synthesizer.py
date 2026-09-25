"""Fact-bound customer-facing responses; live values come only from tool results."""
import re
from langchain_core.messages import AIMessage
from agent.prompts import ar, en, masri

def _prompt(language): return {"ar": ar, "masri": masri}.get(language, en)

def _welcome(language):
    if language == "masri":
        return "أهلاً بيك في صيدلية شفاء 👋 أقدر أساعدك في توفر الأدوية والأسعار والطلبات والتوصيل."
    if language == "ar":
        return "أهلاً بك في صيدلية شفاء 👋 يمكنني مساعدتك في توفر الأدوية والأسعار والطلبات والتوصيل."
    return "Welcome to Shifa Pharmacy 👋 I can help with product availability, prices, orders, and delivery."

def _prefix_first_turn(state, text):
    if state.get("channel") == "messenger" and state.get("is_first_turn") and text and not text.startswith("Welcome") and not text.startswith("أهلاً"):
        return _welcome(state.get("language", "en")) + "\n\n" + text
    return text

def _product_info_reply(item, language):
    name = item.get("name_ar") if language in {"ar", "masri"} else item.get("name")
    description = item.get("short_description") or item.get("generic_name")
    if language == "masri":
        return f"{name}: {description or 'أقدر أوضح الاسم والسعر والتوفر، لكن تفاصيل الاستخدام يحددها الصيدلي.'}"
    if language == "ar":
        return f"{name}: {description or 'يمكنني توضيح الاسم والسعر والتوفر، أما الاستخدام فيحدده الصيدلي.'}"
    return f"{name}: {description or 'I can show its name, price, and availability; a pharmacist should explain its use.'}"


def _catalog_reply(items, language):
    lines = []
    for item in items[:3]:
        name = item["name_ar"] or item["name"] if language in {"ar", "masri"} else item["name"]
        stock = item["stock_quantity"]
        if language == "masri":
            availability = f"متوفر دلوقتي ({stock} قطعة)" if stock else "مش متوفر دلوقتي"
            lines.append(f"{name}: {item['price']} جنيه — {availability}")
        elif language == "ar":
            availability = f"متوفر حاليًا ({stock} قطعة)" if stock else "غير متوفر حاليًا"
            lines.append(f"{name}: {item['price']} جنيه — {availability}")
        else:
            availability = f"available now ({stock} units)" if stock else "currently unavailable"
            lines.append(f"{name}: EGP {item['price']} — {availability}")
    prefix = {"masri": "أيوه، لقيت:", "ar": "نعم، المتاح حاليًا:", "en": "Yes, currently available:"}[language]
    suffix = {"masri": " تحب أساعدك تضيفه للطلب؟", "ar": " هل ترغب في إضافته إلى الطلب؟", "en": " Would you like to add one to an order?"}[language]
    return prefix + "\n- " + "\n- ".join(lines) + suffix


_ARABIC_CATEGORY_NAMES = {
    "pain-relief-cold": "مسكنات وأدوية البرد",
    "vitamins-supplements": "فيتامينات ومكملات",
    "baby-care": "العناية بالأطفال",
    "personal-care": "العناية الشخصية",
    "diabetes-care": "مستلزمات السكري",
    "medical-devices": "أجهزة طبية",
}


def _categories_reply(categories, language):
    if language in {"ar", "masri"}:
        names = [_ARABIC_CATEGORY_NAMES.get(category["slug"], category["name"]) for category in categories]
        prefix = "هذه الفئات المتاحة حاليًا:" if language == "ar" else "دي الفئات المتاحة دلوقتي:"
        suffix = " قل لي الفئة أو اسم المنتج وسأعرض المتاح والسعر."
    else:
        names = [category["name"] for category in categories]
        prefix = "These categories are currently available:"
        suffix = " Tell me a category or product name and I will show the available items and prices."
    return prefix + "\n- " + "\n- ".join(names) + suffix


def _requested_name(query):
    """Remove common storefront phrasing before echoing an unavailable name."""
    cleaned = query.strip().rstrip("؟?!.")
    cleaned = re.sub(r"^في\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:دوا|دواء|ادوية|ادويه)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:do you have|is there|i need)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned or query


def _not_found_reply(query, language):
    name = _requested_name(query)
    if language == "masri":
        return (
            f"ملقتش «{name}» ضمن المنتجات المتاحة دلوقتي. "
            "جرّب الاسم بالإنجليزي أو المادة الفعالة، أو اسأل عن فيتامينات أو أدوية البرد أو منتجات الأطفال."
        )
    if language == "ar":
        return (
            f"لا يظهر «{name}» ضمن المنتجات المتاحة حاليًا. "
            "جرّب كتابة الاسم بالإنجليزية أو المادة الفعالة، أو اسأل عن فئات مثل الفيتامينات وأدوية البرد ومنتجات الأطفال."
        )
    return (
        f"I could not find “{name}” in the current catalog. "
        "Try the English name or active ingredient, or ask to browse vitamins, cold products, or baby care."
    )


def _delivery_reply(retrieved):
    """Keep the delivery quick action focused on its two live KB documents."""
    preferred_titles = {"Delivery areas and fees", "Delivery times"}
    chunks = [item["content"] for item in retrieved if item["metadata"].get("title") in preferred_titles]
    return "\n\n".join(chunks[:2]) if chunks else retrieved[0]["content"]


def _symptom_disclaimer(language):
    if language == "masri":
        return "دي اقتراحات عامة من المنتجات المتاحة، مش تشخيص. كلم الصيدلي لو الأعراض استمرت أو زادت."
    if language == "ar":
        return "هذه اقتراحات عامة من المنتجات المتاحة وليست تشخيصًا. راجع الصيدلي إذا استمرت الأعراض أو ساءت."
    return "These are general suggestions from available products, not a diagnosis. Speak with a pharmacist if symptoms persist or worsen."


def synthesizer(state):
    if state.get("response"):
        text = _prefix_first_turn(state, state["response"])
        return {"response": text, "messages": [AIMessage(content=text)]}
    prompt = _prompt(state.get("language"))
    rationale = (state.get("plan") or {}).get("rationale")
    if state.get("safety_flag") == "rx_required": text = prompt.RX
    elif state.get("order_stage") == "collect_details":
        text = "Please send the recipient name, mobile number, and delivery address." if state.get("language") == "en" else "ابعت اسم المستلم ورقم الموبايل والعنوان علشان أجهز الطلب."
    elif state.get("pending_action"): text = prompt.CONFIRM
    elif (
        state.get("tool_results")
        and state["tool_results"][-1].get("ok")
        and state["tool_results"][-1].get("name") == "create_order"
        and isinstance(state["tool_results"][-1].get("data"), dict)
        and state["tool_results"][-1]["data"].get("order_number")
    ):
        text = prompt.ORDER_CREATED.format(order_number=state["tool_results"][-1]["data"]["order_number"])
    elif (
        state.get("tool_results")
        and state["tool_results"][-1].get("ok")
        and state["tool_results"][-1].get("name") == "get_order_status"
    ):
        order = state["tool_results"][-1]["data"]
        text = f"Order {order['order_number']} is currently {order['status']}."
    elif rationale == "greeting":
        text = _welcome(state.get("language", "en")) + (" اكتب اسم الدواء أو سؤالك." if state.get("language") in {"ar", "masri"} else " Tell me a product name or question.")
    elif rationale == "thanks":
        text = "العفو، أنا تحت أمرك!" if state.get("language") in {"ar", "masri"} else "You're welcome!"
    elif rationale == "order intent without product":
        text = "أكيد، تحب تطلب إيه؟ اكتب اسم الدواء أو المنتج." if state.get("language") in {"ar", "masri"} else "Sure—what would you like to order? Send the product name."
    elif state.get("product_focus"):
        text = _product_info_reply(state["product_focus"], state.get("language", "en"))
    elif state.get("needs_human"):
        text = "A pharmacist will review your request shortly."
    elif state.get("catalog_results"):
        text = _catalog_reply(state["catalog_results"], state.get("language", "en"))
        if state.get("symptom_tier") == "tier1": text += "\n\n" + _symptom_disclaimer(state.get("language", "en"))
    elif (
        state.get("tool_results")
        and state["tool_results"][-1].get("ok")
        and state["tool_results"][-1].get("name") == "list_categories"
    ):
        text = _categories_reply(state["tool_results"][-1]["data"], state.get("language", "en"))
    elif (
        state.get("tool_results")
        and state["tool_results"][-1].get("name") == "search_products"
        and state["tool_results"][-1].get("error_code") == "NO_RESULTS"
    ):
        mentions = (state.get("plan") or {}).get("product_mentions") or ["that product"]
        text = _not_found_reply(mentions[0], state.get("language", "en"))
    elif (state.get("plan") or {}).get("intent") == "sales": text = prompt.UNKNOWN
    elif state.get("retrieved"):
        text = _delivery_reply(state["retrieved"]) if (state.get("plan") or {}).get("rationale") == "delivery, branch, or payment question" else state["retrieved"][0]["content"]
    else: text = prompt.UNKNOWN
    text = _prefix_first_turn(state, text)
    return {"response": text, "messages": [AIMessage(content=text)]}
