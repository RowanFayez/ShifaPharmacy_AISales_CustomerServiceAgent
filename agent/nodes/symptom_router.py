"""Conservative symptom triage before product catalog routing.

This node does not diagnose or recommend a regimen.  It only decides whether
the customer can browse a safe OTC category, needs a pharmacist, or needs one
clarifying question before either path is chosen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from langchain_core.messages import HumanMessage

from agent.lang import normalize_for_retrieval


SymptomTier = Literal["tier1", "tier2", "clarify", "none"]


@dataclass(frozen=True)
class SymptomDecision:
    tier: SymptomTier
    category: str | None = None


def _message(state) -> str:
    return next(
        (message.content.strip() for message in reversed(state.get("messages", [])) if isinstance(message, HumanMessage)),
        "",
    )


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(normalize_for_retrieval(phrase) in text for phrase in phrases)


_DOSAGE_OR_INTERACTION = (
    "dosage", "dose", "how much should i take", "how much medicine", "how often", "drug interaction", "interaction", "mix with",
    "جرعة", "كام قرص", "كل كام", "تفاعل دوائي", "يتعارض", "مع دواء",
)
_RED_FLAGS = (
    "chest pain", "chest tightness", "difficulty breathing", "trouble breathing", "shortness of breath", "cannot breathe",
    "anemia", "iron deficiency", "أنيميا", "فقر دم",
    "anemia", "iron deficiency", "أنيميا", "فقر دم",
    "high fever", "persistent fever", "severe", "worsening", "getting worse", "pregnant", "pregnancy",
    "blood", "bleeding", "vomit blood", "allergic reaction", "anaphylaxis", "swollen lips", "swollen tongue",
    "ألم صدر", "ألم في الصدر", "صدري بيوجعني", "ضيق تنفس", "صعوبة تنفس", "مش قادر اتنفس", "مش عارف اتنفس", "حرارة عالية", "حرارة مستمرة", "حرارتي عالية",
    "شديد", "شديدة", "بتسوء", "بتزيد", "حامل", "حمل", "دم", "نزيف", "قيء دم", "حساسية شديدة",
    "تورم الشفايف", "تورم اللسان",
)
_CHILD_OR_INFANT = ("infant", "baby", "toddler", "child", "kid", "رضيع", "بيبي", "طفل", "طفلي", "ابني", "بنتي")
_SYMPTOM_WORDS = (
    "headache", "cold", "flu", "cough", "throat", "sore throat", "fever", "ache", "pain", "allergy", "rash", "indigestion", "cut",
    "صداع", "برد", "انفلونزا", "كحة", "سعال", "حلق", "حرارة", "وجع", "ألم", "حساسية", "طفح", "حموضة", "عسر هضم", "جرح",
)
_MILD_CATEGORY_MAP: tuple[tuple[str, str], ...] = (
    (("headache", "mild fever", "ache", "minor pain", "صداع", "حرارة بسيطة", "حرارة خفيفة", "وجع", "ألم بسيط"), "pain-relief-cold"),
    (("cold", "flu", "cough", "throat", "sore throat", "برد", "انفلونزا", "كحة", "سعال", "حلق", "زوري"), "pain-relief-cold"),
    (("allergy", "rash", "حساسية", "طفح"), "personal-care"),
    (("indigestion", "حموضة", "عسر هضم"), "pain-relief-cold"),
    (("minor cut", "small cut", "جرح بسيط", "قطع بسيط"), "medical-devices"),
)
_UNCLEAR_HEALTH = ("not feeling well", "feel unwell", "something is wrong", "مش كويس", "مش مرتاح", "تعبان", "تعبانة")


_BACK_SYMPTOMS = ("back pain", "backpain", "وجع الظهر", "ألم الظهر", "وجع الضهر", "ألم الضهر", "Ø§Ù„Ø¸Ù‡Ø±", "Ø§Ù„Ø¶Ù‡Ø±")
_MILD_CLARIFICATION_ANSWERS = (
    "mild", "minor", "light", "manageable", "not serious", "nothing serious", "no warning signs", "just mild",
    "بس خفيف", "بس وجع خفيف", "مجرد وجع بسيط", "مجرد ألم بسيط", "خفيف", "خفيفة", "بسيط", "بسيطة",
    "مش شديد", "مش شديدة", "مش خطير", "مش خطيرة", "مفيش خطر", "مفيش أعراض خطيرة",
    "Ø®ÙÙŠÙ", "Ø®ÙÙŠÙØ©", "Ø¨Ø³ÙŠØ·", "Ø¨Ø³ÙŠØ·Ø©", "Ù…Ø´ Ø´Ø¯ÙŠØ¯", "Ù…Ø´ Ø®Ø·ÙŠØ±",
)
_CLARIFICATION_RED_FLAGS = (
    "severe", "serious", "worsening", "getting worse", "warning sign", "trouble breathing", "difficulty breathing",
    "chest pain", "high fever", "persistent fever", "pregnant", "pregnancy", "blood", "bleeding",
    "allergic reaction", "anaphylaxis", "شديد", "شديدة", "خطير", "خطيرة", "بتزيد", "بتسوء", "تسوء",
    "صعوبة في التنفس", "ضيق تنفس", "ألم صدر", "ألم في الصدر", "حرارة عالية", "حرارة مستمرة", "حامل", "حمل",
    "دم", "نزيف", "حساسية شديدة", "Ø´Ø¯ÙŠØ¯", "Ø´Ø¯ÙŠØ¯Ø©", "Ø®Ø·ÙŠØ±", "Ø¶ÙŠÙ‚ ØªÙ†ÙØ³", "ØµØ¹ÙˆØ¨Ø© ØªÙ†ÙØ³",
)


def classify_symptom(text: str) -> SymptomDecision:
    """Classify a customer health message without naming a diagnosis."""
    normalized = normalize_for_retrieval(text)
    has_symptom = _contains_any(normalized, _SYMPTOM_WORDS) or _contains_any(normalized, _BACK_SYMPTOMS)
    if _contains_any(normalized, _DOSAGE_OR_INTERACTION):
        return SymptomDecision("tier2")
    if _contains_any(normalized, _RED_FLAGS):
        return SymptomDecision("tier2")
    if has_symptom and _contains_any(normalized, _CHILD_OR_INFANT):
        return SymptomDecision("tier2")
    if _contains_any(normalized, _BACK_SYMPTOMS) and not _contains_any(normalized, _MILD_CLARIFICATION_ANSWERS):
        return SymptomDecision("clarify")
    if has_symptom:
        for phrases, category in _MILD_CATEGORY_MAP:
            if _contains_any(normalized, phrases):
                return SymptomDecision("tier1", category)
        return SymptomDecision("clarify")
    if _contains_any(normalized, _UNCLEAR_HEALTH):
        return SymptomDecision("clarify")
    return SymptomDecision("none")


def _clarifying_reply(language: str) -> str:
    if language == "masri":
        return "هل الأعراض خفيفة، ولا في علامة خطرة زي صعوبة في التنفس؟"
    if language == "ar":
        return "هل الأعراض خفيفة، أم توجد علامة خطرة مثل صعوبة في التنفس؟"
    return "Are the symptoms mild, or is there a warning sign such as trouble breathing?"


def _classify_clarification_answer(text: str) -> SymptomDecision | None:
    """Interpret the answer to our one clarification before fresh routing."""
    normalized = normalize_for_retrieval(text)
    if _contains_any(normalized, _CLARIFICATION_RED_FLAGS):
        return SymptomDecision("tier2")
    if _contains_any(normalized, _MILD_CLARIFICATION_ANSWERS):
        return SymptomDecision("tier1", "pain-relief-cold")
    return None


def symptom_router(state):
    """Store a deterministic tier decision for the graph's next branch."""
    text = _message(state)
    awaiting = bool(state.get("awaiting_symptom_clarification"))
    rounds = int(state.get("symptom_clarification_rounds") or 0)
    if awaiting:
        # The next customer message answers our question, rather than starting
        # a new classification. Ambiguity escalates instead of looping.
        decision = _classify_clarification_answer(text) or SymptomDecision("tier2")
        update = {
            "symptom_tier": decision.tier,
            "symptom_category": decision.category,
            "awaiting_symptom_clarification": False,
            "symptom_clarification_rounds": rounds,
        }
    else:
        decision = classify_symptom(text)
        if decision.tier == "clarify" and rounds >= 1:
            decision = SymptomDecision("tier2")
        update = {
            "symptom_tier": decision.tier,
            "symptom_category": decision.category,
            "awaiting_symptom_clarification": decision.tier == "clarify",
            "symptom_clarification_rounds": rounds + 1 if decision.tier == "clarify" else rounds,
        }
    if decision.tier == "clarify":
        update["response"] = _clarifying_reply(state.get("language", "en"))
    return update
