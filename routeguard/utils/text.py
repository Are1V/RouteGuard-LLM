"""Language-aware text normalisation used by scoring, consistency, and grounding.

Normalisation matters more than it looks for multilingual evaluation: Persian and
Dari text mixes Arabic and Persian code points for the same letters (``ي``/``ی``,
``ك``/``ک``) and may use Extended Arabic-Indic digits (``۱۲۳``) or Arabic-Indic
digits (``١٢٣``). Without folding these, exact-match scoring silently penalises
the Persian-script subset and every downstream comparison across languages is biased.
"""

from __future__ import annotations

import re
import unicodedata

_DIGIT_TABLE = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)
_ARABIC_FOLD = str.maketrans(
    {"ي": "ی", "ى": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه", "أ": "ا", "إ": "ا", "آ": "ا"}
)
# Arabic decimal/thousands separators and Persian comma
_SEPARATORS = str.maketrans({"٫": ".", "٬": ",", "،": ","})
_ZERO_WIDTH = dict.fromkeys(map(ord, "‌‍‎‏﻿"), " ")

_EN_ARTICLES = re.compile(r"\b(a|an|the)\b")
_WS = re.compile(r"\s+")


def normalize_digits(text: str) -> str:
    """Map Arabic-Indic / Extended Arabic-Indic digits and separators to ASCII."""
    return text.translate(_DIGIT_TABLE).translate(_SEPARATORS)


def strip_diacritics(text: str) -> str:
    """Remove combining marks (Arabic harakat, Latin accents).

    Cyrillic letters such as ``й`` and ``ё`` decompose into a base letter plus a
    combining mark; we recompose afterwards so they are *not* folded, because in
    Kazakh and Russian they are distinct letters rather than accented variants.
    """
    decomposed = unicodedata.normalize("NFD", text)
    kept: list[str] = []
    for ch in decomposed:
        if unicodedata.category(ch) != "Mn" or (kept and _is_cyrillic(kept[-1])):
            kept.append(ch)
    return unicodedata.normalize("NFC", "".join(kept))


def _is_cyrillic(ch: str) -> bool:
    return "Ѐ" <= ch <= "ӿ"


def normalize_text(text: str, remove_articles: bool = True) -> str:
    """Normalise an answer string for comparison (lowercase, punctuation, script folding)."""
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_ZERO_WIDTH)
    text = normalize_digits(text)
    text = text.translate(_ARABIC_FOLD)
    text = strip_diacritics(text).lower()
    text = "".join(" " if unicodedata.category(ch).startswith("P") else ch for ch in text)
    if remove_articles:
        text = _EN_ARTICLES.sub(" ", text)
    return _WS.sub(" ", text).strip()


def tokenize(text: str) -> list[str]:
    """Whitespace tokenisation of normalised text (script-agnostic)."""
    return normalize_text(text).split()


def char_ngrams(text: str, n: int = 3) -> set[str]:
    t = f" {normalize_text(text)} "
    return {t[i : i + n] for i in range(max(0, len(t) - n + 1))}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)
