"""Task-category classifiers.

* ``rules``   – multilingual regex lexicon + structural cues (no training).
* ``learned`` – character n-gram TF-IDF + logistic regression, fitted on the
  *training split* of a benchmark (never on test items).
* ``given``   – use the category label supplied with the query. This is an
  **oracle** setting for upper-bound analysis only.
* ``none``    – always ``general``; used for the "without task classification" ablation.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from importlib import resources
from pathlib import Path
from typing import Protocol

import numpy as np
import yaml

from routeguard.types import AnswerType, Query

GENERAL = "general"


class TaskClassifier(Protocol):
    name: str

    def classify(self, query: Query) -> tuple[str, float]: ...


def load_lexicon(path: str | Path | None = None) -> tuple[str, dict[str, list[re.Pattern[str]]]]:
    if path is None:
        raw = resources.files("routeguard.resources").joinpath("categories.yaml").read_text("utf-8")
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    compiled = {
        cat: [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns]
        for cat, patterns in data["categories"].items()
    }
    return data.get("default", GENERAL), compiled


class RuleTaskClassifier:
    name = "rules"

    def __init__(self, lexicon: str | Path | None = None):
        self.default, self.patterns = load_lexicon(lexicon)

    def scores(self, query: Query) -> dict[str, float]:
        text = query.text
        scores = {
            cat: float(sum(len(p.findall(text)) for p in pats))
            for cat, pats in self.patterns.items()
        }
        # Structural cues are more reliable than keywords when present.
        if query.answer_type == AnswerType.CODE and "coding" in scores:
            scores["coding"] += 3.0
        if query.context and "reading_comprehension" in scores:
            scores["reading_comprehension"] += 0.75
        if query.answer_type == AnswerType.NUMERIC and "math" in scores:
            scores["math"] += 1.0
        return scores

    def classify(self, query: Query) -> tuple[str, float]:
        scores = self.scores(query)
        total = sum(scores.values())
        if total <= 0:
            return self.default, 0.0
        best = max(scores, key=lambda c: scores[c])
        return best, scores[best] / total


class GivenTaskClassifier:
    """Oracle: trusts the dataset label. Not deployable; for upper-bound analysis."""

    name = "given"

    def classify(self, query: Query) -> tuple[str, float]:
        return (query.category or GENERAL), 1.0


class NullTaskClassifier:
    name = "none"

    def classify(self, query: Query) -> tuple[str, float]:
        return GENERAL, 0.0


class LearnedTaskClassifier:
    """Char n-gram TF-IDF + logistic regression (language-agnostic surface features)."""

    name = "learned"

    def __init__(self, seed: int = 0):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline

        self.model = make_pipeline(
            TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(2, 4),
                min_df=1,
                sublinear_tf=True,
                max_features=50_000,
            ),
            LogisticRegression(max_iter=2000, C=4.0, random_state=seed),
        )
        self.fitted = False
        self.fallback = RuleTaskClassifier()

    def fit(self, queries: Sequence[Query]) -> LearnedTaskClassifier:
        labelled = [q for q in queries if q.category]
        labels = {q.category for q in labelled}
        if len(labels) < 2:
            # A single-category training set cannot train a discriminative classifier.
            self.fitted = False
            return self
        self.model.fit([q.text for q in labelled], [q.category for q in labelled])
        self.fitted = True
        return self

    def classify(self, query: Query) -> tuple[str, float]:
        if not self.fitted:
            return self.fallback.classify(query)
        proba = self.model.predict_proba([query.text])[0]
        idx = int(np.argmax(proba))
        return str(self.model.classes_[idx]), float(proba[idx])


def build_task_classifier(kind: str, lexicon: str | None = None, seed: int = 0) -> TaskClassifier:
    if kind == "rules":
        return RuleTaskClassifier(lexicon)
    if kind == "learned":
        return LearnedTaskClassifier(seed=seed)
    if kind == "given":
        return GivenTaskClassifier()
    if kind == "none":
        return NullTaskClassifier()
    raise ValueError(f"Unknown task classifier '{kind}'. Choose from rules|learned|given|none.")
