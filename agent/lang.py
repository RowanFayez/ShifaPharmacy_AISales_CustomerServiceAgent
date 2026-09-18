"""Arabic normalization shared by indexing and retrieval."""

from __future__ import annotations

import re


_TASHKEEL = re.compile("[\u0617-\u061A\u064B-\u0652\u0670]")
_TATWEEL = "ـ"


def normalize_arabic(text: str) -> str:
    """Normalize Arabic spelling variants without translating user content."""
    normalized = _TASHKEEL.sub("", text)
    normalized = normalized.replace(_TATWEEL, "")
    normalized = normalized.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"}))
    return normalized


def normalize_for_retrieval(text: str) -> str:
    """Apply stable whitespace and Arabic normalization for embedding input and cache keys."""
    return " ".join(normalize_arabic(text).casefold().split())

def detect_language(text: str) -> str:
    """Small deterministic detector; Masri markers take precedence over Arabic script."""
    lowered = normalize_for_retrieval(text)
    if any(marker in lowered for marker in ("يا", "عايز", "عايزه", "بكام", "ازاي", "اسطا")): return "masri"
    return "ar" if any("\u0600" <= char <= "\u06ff" for char in text) else "en"
