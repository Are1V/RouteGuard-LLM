"""Answer extraction and canonicalisation.

Every prompt template asks the model to end with ``Final answer: <answer>``.
Extraction first looks for that marker (and a few localised variants models
produce when answering in the query language), then falls back to type-specific
heuristics. Extraction failures return ``None`` and are counted separately from
wrong answers in the error analysis.
"""

from __future__ import annotations

import re

from routeguard.types import AnswerType
from routeguard.utils.text import normalize_digits, normalize_text

FINAL_MARKERS = [
    r"final answer",
    r"answer",
    r"окончательный ответ",
    r"ответ",
    r"соңғы жауап",
    r"жауап",
    r"پاسخ نهایی",
    r"جواب نهایی",
    r"پاسخ",
    r"جواب",
]
_MARKER_RE = re.compile(
    r"(?:\*\*)?(?:" + "|".join(FINAL_MARKERS) + r")(?:\*\*)?\s*[:：]\s*(?:\*\*)?(.+)",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"[-−]?\d[\d,]*(?:\.\d+)?")
_CODE_BLOCK_RE = re.compile(r"```(?:python|py|Python)?[ \t]*\n(.*?)```", re.DOTALL)
# Uppercase Cyrillic look-alikes models occasionally emit instead of Latin option letters.
# Only applied inside the final-answer segment: in free Russian text "В" is a common word.
_LETTER_FOLD = str.maketrans({"А": "A", "В": "B", "С": "C", "Д": "D", "Е": "E"})


def _final_segment(text: str) -> str | None:
    matches = list(_MARKER_RE.finditer(text))
    if not matches:
        return None
    return matches[-1].group(1).strip()


def canonical_number(raw: str) -> str | None:
    """Canonical string form of a number (``"1,234.50"`` -> ``"1234.5"``)."""
    s = normalize_digits(raw).replace("−", "-").replace(",", "").strip()
    try:
        value = float(s)
    except ValueError:
        return None
    if value.is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def extract_numeric(text: str) -> str | None:
    text = normalize_digits(text)
    segment = _final_segment(text)
    for source in (segment, text):
        if not source:
            continue
        numbers = _NUMBER_RE.findall(source)
        if numbers:
            # In the marker segment the first number is the answer; in free text the last one.
            candidate = numbers[0] if source is segment else numbers[-1]
            return canonical_number(candidate)
    return None


def extract_choice(text: str, choices: list[str] | None = None) -> str | None:
    n = len(choices) if choices else 4
    letters = "ABCDEFGHIJ"[:n]
    letter_re = re.compile(rf"(?<!\w)\(?([{letters}])\)?(?!\w)")
    segment = _final_segment(text)
    if segment is not None:
        m = letter_re.search(segment.translate(_LETTER_FOLD))
        if m:
            return m.group(1)
        matched = _match_choice_text(segment, choices, letters)
        if matched:
            return matched
    m = re.search(rf"(?i:answer|option|choice)\s*(?:is|:)?\s*\(?([{letters}])\)?(?!\w)", text)
    if m:
        return m.group(1)
    m = re.fullmatch(rf"\(?([{letters}])\)?[.)]?", text.strip())
    if m:
        return m.group(1)
    return _match_choice_text(text, choices, letters)


def _match_choice_text(text: str, choices: list[str] | None, letters: str) -> str | None:
    if not choices:
        return None
    target = normalize_text(text)
    for i, choice in enumerate(choices):
        if normalize_text(choice) and normalize_text(choice) == target:
            return letters[i]
    return None


def extract_code(text: str) -> str | None:
    blocks = _CODE_BLOCK_RE.findall(text)
    if blocks:
        return max(blocks, key=len).strip("\n")
    if re.search(r"^\s*(def |class |import |from )", text, re.MULTILINE):
        return text.strip()
    return None


def extract_text(text: str) -> str | None:
    segment = _final_segment(text)
    if segment is not None:
        return segment.splitlines()[0].strip().strip("*").strip() or None
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else None


def extract_answer(
    text: str, answer_type: AnswerType, choices: list[str] | None = None
) -> str | None:
    if answer_type == AnswerType.NUMERIC:
        return extract_numeric(text)
    if answer_type == AnswerType.CHOICE:
        return extract_choice(text, choices)
    if answer_type == AnswerType.CODE:
        return extract_code(text)
    return extract_text(text)


def answers_equivalent(a: str | None, b: str | None, answer_type: AnswerType) -> bool:
    """Whether two *predicted* answers agree (used by self-consistency, not scoring)."""
    if a is None or b is None:
        return False
    if answer_type == AnswerType.NUMERIC:
        ca, cb = canonical_number(a), canonical_number(b)
        return ca is not None and ca == cb
    if answer_type == AnswerType.CHOICE:
        return a.strip().upper() == b.strip().upper()
    if answer_type == AnswerType.CODE:
        return re.sub(r"\s+", "", a) == re.sub(r"\s+", "", b)
    return normalize_text(a) == normalize_text(b)
