"""Lightweight, dependency-free language identification.

The detector works in two stages:

1. **Script identification** from Unicode ranges (Latin / Cyrillic / Arabic / ...).
2. **Within-script disambiguation** using letters that are distinctive for a
   language inside its script (e.g. Kazakh ``ә ғ қ ң ө ұ ү һ і`` vs Russian, or
   Persian ``پ چ ژ گ`` vs Arabic) plus short stopword lists.

This is intentionally simple and transparent so that *language-identification
errors can be measured* as a separate failure source instead of being hidden in
an opaque model. It does **not** distinguish Dari from Iranian Persian: both are
reported as ``fa`` because short queries rarely contain reliable lexical cues.
Dataset-provided variants (e.g. Belebele ``prs_Arab``) are preserved in item
metadata instead.

To add a language, register a :class:`LanguageProfile` with :func:`register_language`.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

SCRIPT_RANGES: dict[str, list[tuple[int, int]]] = {
    "Latin": [(0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x024F)],
    "Cyrillic": [(0x0400, 0x04FF), (0x0500, 0x052F)],
    "Arabic": [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    "Greek": [(0x0370, 0x03FF)],
    "Devanagari": [(0x0900, 0x097F)],
    "Han": [(0x4E00, 0x9FFF)],
}


@dataclass(frozen=True)
class LanguageProfile:
    code: str
    name: str
    script: str
    marker_chars: str = ""
    stopwords: frozenset[str] = field(default_factory=frozenset)
    prior: float = 0.0  # tie-breaker within a script (higher wins)


_PROFILES: dict[str, LanguageProfile] = {}


def register_language(profile: LanguageProfile) -> None:
    _PROFILES[profile.code] = profile


def registered_languages() -> dict[str, LanguageProfile]:
    return dict(_PROFILES)


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


for _p in [
    LanguageProfile(
        "en", "English", "Latin", "",
        _words("the a an is are was of and to in what which who how many does do for with that "
               "this on by from it be"),
        prior=1.0,
    ),
    LanguageProfile(
        "kk", "Kazakh", "Cyrillic", "әғқңөұүһі",
        _words("және бұл мен үшін қандай неше қанша не кім бар жоқ ол осы деген болып болады "
               "ма ме ба бе па пе да де та те"),
    ),
    LanguageProfile(
        "ru", "Russian", "Cyrillic", "ёэщъ",
        _words("и в не что на это как сколько какой какая кто с по из для был была его она они "
               "к у же от все так"),
        prior=1.0,
    ),
    LanguageProfile(
        "fa", "Persian (incl. Dari)", "Arabic", "پچژگ",
        _words("است که را این از به چه کدام در با و یک برای آن می هست بود شد چند چقدر کجا"),
        prior=1.0,
    ),
    LanguageProfile(
        "ar", "Arabic", "Arabic", "ةى",
        _words("في من على ما هل هو هي التي الذي إلى عن كان أن"),
    ),
]:  # fmt: skip
    register_language(_p)

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _script_of(ch: str) -> str | None:
    cp = ord(ch)
    for script, ranges in SCRIPT_RANGES.items():
        if any(lo <= cp <= hi for lo, hi in ranges):
            return script
    return None


def script_distribution(text: str) -> dict[str, float]:
    """Fraction of alphabetic characters belonging to each script."""
    counts: Counter[str] = Counter()
    for ch in text:
        if unicodedata.category(ch).startswith("L"):
            counts[_script_of(ch) or "Other"] += 1
    total = sum(counts.values())
    return {s: c / total for s, c in counts.most_common()} if total else {}


@dataclass
class LanguageDetection:
    language: str
    confidence: float
    scripts: dict[str, float]
    mixed_script: bool


class LanguageDetector:
    """Script + marker-letter + stopword language identifier."""

    name = "script"

    def __init__(self, languages: list[str] | None = None, mixed_threshold: float = 0.2):
        profiles = registered_languages()
        unknown = [code for code in languages or [] if code not in profiles]
        if unknown:
            raise ValueError(f"No language profile registered for {unknown}")
        self.profiles = [profiles[c] for c in (languages or profiles)]
        self.mixed_threshold = mixed_threshold

    def detect(self, text: str) -> LanguageDetection:
        scripts = script_distribution(text)
        if not scripts:
            return LanguageDetection("und", 0.0, {}, False)
        # Code and formulas are Latin-heavy; if a non-Latin script holds a substantial share,
        # it is the natural-language script of the query.
        non_latin = {s: v for s, v in scripts.items() if s != "Latin"}
        primary = (
            max(non_latin, key=lambda s: non_latin[s])
            if non_latin and max(non_latin.values()) >= 0.3
            else max(scripts, key=lambda s: scripts[s])
        )
        secondary = sorted(scripts.values(), reverse=True)[1] if len(scripts) > 1 else 0.0
        candidates = [p for p in self.profiles if p.script == primary]
        if not candidates:
            return LanguageDetection("und", 0.0, scripts, secondary >= self.mixed_threshold)
        if len(candidates) == 1:
            return LanguageDetection(
                candidates[0].code,
                round(scripts[primary], 4),
                scripts,
                secondary >= self.mixed_threshold,
            )

        lowered = text.lower()
        words = _WORD_RE.findall(lowered)
        n_letters = max(1, sum(1 for ch in lowered if _script_of(ch) == primary))
        scores: dict[str, float] = {}
        for p in candidates:
            marker_rate = sum(lowered.count(c) for c in p.marker_chars) / n_letters
            stop_rate = sum(1 for w in words if w in p.stopwords) / max(1, len(words))
            scores[p.code] = 10.0 * marker_rate + 2.0 * stop_rate + 1e-3 * p.prior
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        best, best_score = ranked[0]
        runner_up = ranked[1][1]
        margin = (best_score - runner_up) / (best_score + 1e-9) if best_score > 0 else 0.0
        confidence = scripts[primary] * (0.5 + 0.5 * min(1.0, margin))
        return LanguageDetection(
            best, round(confidence, 4), scripts, secondary >= self.mixed_threshold
        )
