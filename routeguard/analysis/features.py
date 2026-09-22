"""Hand-crafted query features used by the heuristic difficulty baseline and as
side-information for learned estimators and routers."""

from __future__ import annotations

import math
import re

from routeguard.types import Query
from routeguard.utils.text import normalize_digits

_MATH_OPS = re.compile(r"[+\-*/^=<>×÷√∑∫%]|\\frac|\\sqrt|\bmod\b")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_CODE = re.compile(r"```|\bdef \w+\(|\bclass \w+|\breturn\b|;\s*$|\{\s*$|=>|\bimport \w+", re.M)
_ENTITY = re.compile(r"(?<=[^.!?]\s)[A-ZА-ЯЁӘҒҚҢӨҰҮҺІ][\w-]+")
_SENTENCE = re.compile(r"[.!?؟。]+(?:\s|$)")

# Multilingual cue words (en / ru / kk / fa). Kept short and auditable on purpose.
STEP_CUES = (
    "step",
    "explain",
    "prove",
    "why",
    "derive",
    "compare",
    "analy",
    "justify",
    "first",
    "then",
    "шаг",
    "объясн",
    "докаж",
    "почему",
    "сравн",
    "сначала",
    "затем",
    "қадам",
    "түсіндір",
    "дәлелде",
    "неге",
    "салыстыр",
    "алдымен",
    "مرحله",
    "توضیح",
    "اثبات",
    "چرا",
    "مقایسه",
    "ابتدا",
    "سپس",
)
CONSTRAINT_CUES = (
    "exactly",
    "at least",
    "at most",
    "must",
    "without",
    "only",
    "each",
    "every",
    "all",
    "ровно",
    "не менее",
    "не более",
    "должен",
    "без",
    "только",
    "каждый",
    "дәл",
    "кемінде",
    "тек",
    "әрбір",
    "دقیقا",
    "حداقل",
    "حداکثر",
    "باید",
    "بدون",
    "فقط",
    "هر",
)

FEATURE_NAMES = [
    "log_chars",
    "log_words",
    "n_sentences",
    "n_numbers",
    "n_math_ops",
    "has_code",
    "n_entities",
    "n_question_marks",
    "step_cues",
    "constraint_cues",
    "n_choices",
    "has_context",
    "log_context_chars",
    "avg_word_len",
    "digit_ratio",
    "non_latin_ratio",
]


def extract_features(query: Query, non_latin_ratio: float = 0.0) -> dict[str, float]:
    text = normalize_digits(query.text)
    lowered = text.lower()
    words = text.split()
    n_chars = len(text)
    context_chars = len(query.context or "")
    return {
        "log_chars": math.log1p(n_chars),
        "log_words": math.log1p(len(words)),
        "n_sentences": float(max(1, len(_SENTENCE.findall(text)))),
        "n_numbers": float(len(_NUMBER.findall(text))),
        "n_math_ops": float(len(_MATH_OPS.findall(text))),
        "has_code": float(bool(_CODE.search(text))),
        "n_entities": float(len(_ENTITY.findall(text))),
        "n_question_marks": float(text.count("?") + text.count("؟")),
        "step_cues": float(sum(lowered.count(c) for c in STEP_CUES)),
        "constraint_cues": float(sum(lowered.count(c) for c in CONSTRAINT_CUES)),
        "n_choices": float(len(query.choices or [])),
        "has_context": float(bool(query.context)),
        "log_context_chars": math.log1p(context_chars),
        "avg_word_len": (sum(len(w) for w in words) / len(words)) if words else 0.0,
        "digit_ratio": (sum(ch.isdigit() for ch in text) / n_chars) if n_chars else 0.0,
        "non_latin_ratio": non_latin_ratio,
    }
