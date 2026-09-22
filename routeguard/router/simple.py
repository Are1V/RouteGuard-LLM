"""Non-learned routers: fixed model, random, rule-based, and difficulty thresholds."""

from __future__ import annotations

import random
from typing import Any, ClassVar

from routeguard.context import CallContext
from routeguard.models.pool import ModelPool
from routeguard.router.base import BaseRouter
from routeguard.types import DifficultyEstimate, Query, QueryAnalysis, RoutingDecision
from routeguard.utils.seeding import derive_seed


class FixedRouter(BaseRouter):
    """Always the same model (the ``always-small/medium/large`` baselines)."""

    name = "fixed"

    def __init__(self, pool: ModelPool, model: str | None = None):
        super().__init__(pool)
        self.model = model or pool.strongest
        pool.spec(self.model)  # validate

    def route(
        self,
        query: Query,
        analysis: QueryAnalysis,
        difficulty: DifficultyEstimate,
        ctx: CallContext,
    ) -> RoutingDecision:
        return RoutingDecision(self.model, self.name, reason="fixed")


class RandomRouter(BaseRouter):
    """Router 1. Uniform (or weighted) random choice; deterministic per (seed, query id)."""

    name = "random"

    def __init__(self, pool: ModelPool, weights: dict[str, float] | None = None, seed: int = 0):
        super().__init__(pool)
        self.weights = [float((weights or {}).get(n, 1.0)) for n in pool.names]
        self.seed = seed

    def route(
        self,
        query: Query,
        analysis: QueryAnalysis,
        difficulty: DifficultyEstimate,
        ctx: CallContext,
    ) -> RoutingDecision:
        rng = random.Random(derive_seed("random-router", self.seed, query.id, query.text))
        model = rng.choices(self.pool.names, weights=self.weights)[0]
        return RoutingDecision(model, self.name, reason="random")


class RuleRouter(BaseRouter):
    """Router 2. Ordered, human-readable rules; the first matching rule wins.

    Each rule is ``{"when": {<field>: [values...]}, "model": <name>}`` where field is
    one of ``category``, ``language``, ``difficulty`` (label). Model names may also be
    the aliases ``cheapest`` / ``strongest`` / ``tier:<k>``.
    """

    name = "rules"
    DEFAULT_RULES: ClassVar[list[dict[str, Any]]] = [
        {"when": {"difficulty": ["hard"]}, "model": "strongest"},
        {"when": {"category": ["coding", "math", "logic"]}, "model": "tier:1"},
        {"when": {"language": ["kk", "fa"]}, "model": "tier:1"},
    ]

    def __init__(
        self, pool: ModelPool, rules: list[dict[str, Any]] | None = None, default: str = "cheapest"
    ):
        super().__init__(pool)
        self.rules = rules if rules is not None else self.DEFAULT_RULES
        self.default = default
        for rule in self.rules:
            unknown = set(rule.get("when", {})) - {"category", "language", "difficulty"}
            if unknown:
                raise ValueError(f"Unknown rule fields {unknown}")
            self._resolve(rule["model"])
        self._resolve(default)

    def _resolve(self, alias: str) -> str:
        if alias == "cheapest":
            return self.pool.cheapest
        if alias == "strongest":
            return self.pool.strongest
        if alias.startswith("tier:"):
            return self.pool.by_tier(int(alias.split(":", 1)[1]))
        self.pool.spec(alias)
        return alias

    def route(
        self,
        query: Query,
        analysis: QueryAnalysis,
        difficulty: DifficultyEstimate,
        ctx: CallContext,
    ) -> RoutingDecision:
        values = {
            "category": analysis.category,
            "language": analysis.language,
            "difficulty": difficulty.label.value,
        }
        for i, rule in enumerate(self.rules):
            if all(values[f] in allowed for f, allowed in rule.get("when", {}).items()):
                return RoutingDecision(self._resolve(rule["model"]), self.name, reason=f"rule {i}")
        return RoutingDecision(self._resolve(self.default), self.name, reason="default")


class ThresholdRouter(BaseRouter):
    """Router 3. Partition the difficulty score into ``len(pool)`` bins.

    ``thresholds`` must be increasing with ``len(pool) - 1`` values; by default the
    unit interval is split evenly. Works for any number of models.
    """

    name = "threshold"

    def __init__(self, pool: ModelPool, thresholds: list[float] | None = None):
        super().__init__(pool)
        n = len(pool)
        self.thresholds = thresholds if thresholds is not None else [i / n for i in range(1, n)]
        if len(self.thresholds) != n - 1 or sorted(self.thresholds) != list(self.thresholds):
            raise ValueError(
                f"threshold router needs {n - 1} increasing thresholds for {n} models, "
                f"got {self.thresholds}"
            )

    def route(
        self,
        query: Query,
        analysis: QueryAnalysis,
        difficulty: DifficultyEstimate,
        ctx: CallContext,
    ) -> RoutingDecision:
        tier = sum(difficulty.score >= t for t in self.thresholds)
        return RoutingDecision(
            self.pool.by_tier(tier),
            self.name,
            scores={"difficulty": difficulty.score},
            reason=f"difficulty {difficulty.score:.2f} -> tier {tier}",
        )
