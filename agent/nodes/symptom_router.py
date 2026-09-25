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


def classify_symptom(text: str) -> SymptomDecision:
    """Classify a customer health message without naming a diagnosis."""
    normalized = normalize_for_retrieval(text)
    has_symptom = _contains_any(normalized, _SYMPTOM_WORDS)
    if _contains_any(normalized, _DOSAGE_OR_INTERACTION):
        return SymptomDecision("tier2")
    if _contains_any(normalized, _RED_FLAGS):
        return SymptomDecision("tier2")
    if has_symptom and _contains_any(normalized, _CHILD_OR_INFANT):
        return SymptomDecision("tier2")
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


def symptom_router(state):
    """Store a deterministic tier decision for the graph's next branch."""
    decision = classify_symptom(_message(state))
    update = {"symptom_tier": decision.tier, "symptom_category": decision.category}
    if decision.tier == "clarify":
        update["response"] = _clarifying_reply(state.get("language", "en"))
    return update
