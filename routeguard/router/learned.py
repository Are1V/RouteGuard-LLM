"""Learned routers (Routers 4-6).

* :class:`LearnedRouter` (Router 4) – multiclass classifier over the
  cheapest-correct tier; routes to the predicted tier.
* :class:`CostAwareRouter` (Router 5) – per-model success predictors
  ``p_m(x) = P(model m correct | x)``; routes to the *cheapest* model whose
  predicted success reaches ``target``.
* :class:`QualityCostRouter` (Router 6) – maximises
  ``p_m(x) - lambda * cost_m - mu * latency_m`` (costs normalised to [0, 1]).
  Sweeping ``lambda`` traces a quality/cost Pareto front.

All are trained on training-split outcomes only.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from routeguard.analysis.vectorize import QueryVectorizer, build_embedder
from routeguard.complexity.base import TrainingExample, cheapest_correct_tier
from routeguard.complexity.learned import ProbabilisticTierModel, make_classifier
from routeguard.context import CallContext
from routeguard.models.pool import ModelPool
from routeguard.router.base import BaseRouter
from routeguard.types import DifficultyEstimate, Query, QueryAnalysis, RoutingDecision


class _VectorRouter(BaseRouter):
    requires_fit = True

    def __init__(
        self,
        pool: ModelPool,
        classifier: str = "logistic_regression",
        embedder: str = "hashing",
        use_embedding: bool = True,
        seed: int = 0,
        use_difficulty: bool = True,
        classifier_options: dict[str, Any] | None = None,
    ):
        super().__init__(pool)
        self.classifier = classifier
        self.classifier_options = classifier_options or {}
        self.seed = seed
        self.use_difficulty = use_difficulty
        self.vectorizer = QueryVectorizer(build_embedder(embedder), use_embedding=use_embedding)
        self.fitted = False
        self.trained_ids: set[str] = set()

    def _x(
        self,
        queries: Sequence[Query],
        analyses: Sequence[QueryAnalysis],
        difficulties: Sequence[float] | None,
    ) -> np.ndarray:
        x = self.vectorizer.transform(queries, analyses)
        if self.use_difficulty and difficulties is not None:
            x = np.hstack([x, np.asarray(difficulties, dtype=np.float32)[:, None]])
        return x

    def _fit_vectorizer(self, examples: Sequence[TrainingExample]) -> np.ndarray:
        if not examples:
            raise ValueError(f"{self.name} router needs training examples")
        analyses = [e.analysis for e in examples]
        self.vectorizer.fit(analyses)
        difficulties = [e.difficulty for e in examples] if self.use_difficulty else None
        self.trained_ids = {e.query.id for e in examples}
        return self._x([e.query for e in examples], analyses, difficulties)

    def _check(self) -> None:
        if not self.fitted:
            raise RuntimeError(f"{self.name} router used before fit()")


class LearnedRouter(_VectorRouter):
    name = "learned"

    def fit(self, examples: Sequence[TrainingExample]) -> None:
        x = self._fit_vectorizer(examples)
        y = np.array([cheapest_correct_tier(e.outcomes, self.pool.names) for e in examples])
        self.model = ProbabilisticTierModel(
            make_classifier(self.classifier, self.seed, **self.classifier_options)
        ).fit(x, y)
        self.fitted = True

    def route(
        self,
        query: Query,
        analysis: QueryAnalysis,
        difficulty: DifficultyEstimate,
        ctx: CallContext,
    ) -> RoutingDecision:
        self._check()
        x = self._x([query], [analysis], [difficulty.score])
        proba = self.model.predict_proba(x, len(self.pool) + 1)[0]
        tier = int(np.argmax(proba))
        # Tier N means "no model is predicted to succeed": use the strongest.
        model = self.pool.by_tier(min(tier, len(self.pool) - 1))
        scores = {f"tier_{t}": round(float(p), 4) for t, p in enumerate(proba)}
        return RoutingDecision(model, self.name, scores, reason=f"predicted tier {tier}")


class ModelSuccessPredictor:
    """One binary success classifier per model."""

    def __init__(self, pool: ModelPool, classifier: str, seed: int, options: dict[str, Any]):
        self.pool = pool
        self.models = {
            n: ProbabilisticTierModel(make_classifier(classifier, seed, **options))
            for n in pool.names
        }

    def fit(self, x: np.ndarray, examples: Sequence[TrainingExample]) -> None:
        for name, model in self.models.items():
            model.fit(x, np.array([int(bool(e.outcomes.get(name))) for e in examples]))

    def predict(self, x: np.ndarray) -> dict[str, float]:
        return {n: float(m.predict_proba(x, 2)[0, 1]) for n, m in self.models.items()}


class CostAwareRouter(_VectorRouter):
    name = "cost_aware"

    def __init__(self, pool: ModelPool, target: float = 0.7, **kwargs: Any):
        super().__init__(pool, **kwargs)
        self.target = target

    def fit(self, examples: Sequence[TrainingExample]) -> None:
        x = self._fit_vectorizer(examples)
        self.predictor = ModelSuccessPredictor(
            self.pool, self.classifier, self.seed, self.classifier_options
        )
        self.predictor.fit(x, examples)
        self.fitted = True

    def route(
        self,
        query: Query,
        analysis: QueryAnalysis,
        difficulty: DifficultyEstimate,
        ctx: CallContext,
    ) -> RoutingDecision:
        self._check()
        p = self.predictor.predict(self._x([query], [analysis], [difficulty.score]))
        for name in self.pool.names:  # ascending cost
            if p[name] >= self.target:
                return RoutingDecision(name, self.name, p, reason=f"cheapest with p>={self.target}")
        best = max(p, key=lambda n: p[n])
        return RoutingDecision(best, self.name, p, reason="no model reaches target; max p")


class QualityCostRouter(_VectorRouter):
    name = "quality_cost"

    def __init__(
        self, pool: ModelPool, cost_weight: float = 0.3, latency_weight: float = 0.0, **kwargs: Any
    ):
        super().__init__(pool, **kwargs)
        self.cost_weight = cost_weight
        self.latency_weight = latency_weight
        self.latency: dict[str, float] = {}

    def fit(self, examples: Sequence[TrainingExample]) -> None:
        x = self._fit_vectorizer(examples)
        self.predictor = ModelSuccessPredictor(
            self.pool, self.classifier, self.seed, self.classifier_options
        )
        self.predictor.fit(x, examples)
        mean_lat = {
            n: float(np.mean([e.latency.get(n, 0.0) for e in examples])) for n in self.pool.names
        }
        top = max(mean_lat.values()) or 1.0
        self.latency = {n: v / top for n, v in mean_lat.items()}
        self.fitted = True

    def route(
        self,
        query: Query,
        analysis: QueryAnalysis,
        difficulty: DifficultyEstimate,
        ctx: CallContext,
    ) -> RoutingDecision:
        self._check()
        p = self.predictor.predict(self._x([query], [analysis], [difficulty.score]))
        cost = self.pool.normalized_costs()
        utility = {
            n: p[n] - self.cost_weight * cost[n] - self.latency_weight * self.latency.get(n, 0)
            for n in self.pool.names
        }
        best = max(utility, key=lambda n: utility[n])
        scores = {
            **{f"p_{n}": round(v, 4) for n, v in p.items()},
            **{f"u_{n}": round(v, 4) for n, v in utility.items()},
        }
        return RoutingDecision(best, self.name, scores, reason="max utility")
