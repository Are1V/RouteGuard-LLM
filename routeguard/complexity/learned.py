"""Baselines B and C: supervised difficulty estimators.

Both predict the *cheapest-correct tier* (see :func:`cheapest_correct_tier`) from
query vectors and convert the class probabilities into a continuous score
``E[tier] / n_models``. Targets come from running every pool model on the
**training split** only.

* Baseline B (``learned``): logistic regression, random forest, or XGBoost.
* Baseline C (``neural``): a small multilayer perceptron (scikit-learn), which
  avoids a hard PyTorch dependency for a model of this size.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from routeguard.analysis.vectorize import QueryVectorizer, build_embedder
from routeguard.complexity.base import (
    BaseDifficultyEstimator,
    DifficultyThresholds,
    TrainingExample,
    cheapest_correct_tier,
)
from routeguard.context import CallContext
from routeguard.types import Query, QueryAnalysis
from routeguard.utils.imports import require


def make_classifier(kind: str, seed: int, **kwargs: Any) -> Any:
    """Construct a scikit-learn compatible probabilistic classifier."""
    if kind == "logistic_regression":
        from sklearn.linear_model import LogisticRegression

        return LogisticRegression(max_iter=3000, C=kwargs.get("C", 1.0), random_state=seed)
    if kind == "random_forest":
        from sklearn.ensemble import RandomForestClassifier

        return RandomForestClassifier(
            n_estimators=kwargs.get("n_estimators", 300),
            min_samples_leaf=kwargs.get("min_samples_leaf", 3),
            random_state=seed,
            n_jobs=-1,
        )
    if kind == "xgboost":
        xgb = require("xgboost", "xgboost", "The XGBoost classifier")
        return xgb.XGBClassifier(
            n_estimators=kwargs.get("n_estimators", 300),
            max_depth=kwargs.get("max_depth", 4),
            learning_rate=kwargs.get("learning_rate", 0.05),
            subsample=0.9,
            random_state=seed,
            verbosity=0,
        )
    if kind == "mlp":
        from sklearn.neural_network import MLPClassifier

        return MLPClassifier(
            hidden_layer_sizes=tuple(kwargs.get("hidden", (128, 64))),
            alpha=kwargs.get("alpha", 1e-3),
            max_iter=kwargs.get("max_iter", 500),
            early_stopping=kwargs.get("early_stopping", False),
            random_state=seed,
        )
    raise ValueError(f"Unknown classifier '{kind}' (logistic_regression|random_forest|xgboost|mlp)")


class ProbabilisticTierModel:
    """Classifier over tiers that tolerates tiers absent from the training data."""

    def __init__(self, classifier: Any):
        self.classifier = classifier
        self.classes: np.ndarray = np.array([])
        self.constant: int | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> ProbabilisticTierModel:
        self.classes = np.unique(y)
        if len(self.classes) == 1:
            self.constant = int(self.classes[0])
            return self
        # Re-index labels to 0..k-1 (required by XGBoost).
        index = {c: i for i, c in enumerate(self.classes)}
        self.classifier.fit(x, np.array([index[v] for v in y]))
        return self

    def predict_proba(self, x: np.ndarray, n_tiers: int) -> np.ndarray:
        out = np.zeros((x.shape[0], n_tiers))
        if self.constant is not None:
            out[:, self.constant] = 1.0
            return out
        proba = self.classifier.predict_proba(x)
        for j, c in enumerate(self.classes):
            out[:, int(c)] = proba[:, j]
        return out


class LearnedDifficultyEstimator(BaseDifficultyEstimator):
    name = "learned"
    requires_fit = True
    default_classifier = "logistic_regression"

    def __init__(
        self,
        thresholds: DifficultyThresholds | None = None,
        classifier: str | None = None,
        embedder: str = "hashing",
        use_embedding: bool = True,
        seed: int = 0,
        classifier_options: dict[str, Any] | None = None,
    ):
        super().__init__(thresholds)
        self.classifier_kind = classifier or self.default_classifier
        self.vectorizer = QueryVectorizer(build_embedder(embedder), use_embedding=use_embedding)
        self.model = ProbabilisticTierModel(
            make_classifier(self.classifier_kind, seed, **(classifier_options or {}))
        )
        self.n_tiers = 0
        self.trained_ids: set[str] = set()

    def fit(self, examples: Sequence[TrainingExample], model_order: Sequence[str]) -> None:
        if not examples:
            raise ValueError(f"{self.name} difficulty estimator needs training examples")
        self.n_tiers = len(model_order) + 1
        analyses = [e.analysis for e in examples]
        self.vectorizer.fit(analyses)
        x = self.vectorizer.transform([e.query for e in examples], analyses)
        y = np.array([cheapest_correct_tier(e.outcomes, model_order) for e in examples])
        self.model.fit(x, y)
        self.trained_ids = {e.query.id for e in examples}

    def score(self, query: Query, analysis: QueryAnalysis, ctx: CallContext) -> tuple[float, dict]:
        if self.n_tiers == 0:
            raise RuntimeError(f"{self.name} difficulty estimator used before fit()")
        x = self.vectorizer.transform([query], [analysis])
        proba = self.model.predict_proba(x, self.n_tiers)[0]
        expected_tier = float(np.dot(proba, np.arange(self.n_tiers)))
        score = expected_tier / (self.n_tiers - 1)
        return score, {
            "tier_proba": [round(float(p), 4) for p in proba],
            "classifier": self.classifier_kind,
        }


class NeuralDifficultyEstimator(LearnedDifficultyEstimator):
    name = "neural"
    default_classifier = "mlp"
