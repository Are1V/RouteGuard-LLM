"""Oracle routing — an upper bound, **not a deployable router**.

The oracle looks up which models answer a query correctly (obtained by running
every model on the evaluation split) and picks the cheapest correct one. If no
model is correct it picks the cheapest model, since spending more cannot help;
the oracle is therefore optimal in both accuracy and cost for a fixed pool. It
quantifies the headroom available to any router given that pool and must never
be reported as a method.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from routeguard.complexity.base import cheapest_correct_tier
from routeguard.context import CallContext
from routeguard.models.pool import ModelPool
from routeguard.router.base import BaseRouter
from routeguard.types import DifficultyEstimate, Query, QueryAnalysis, RoutingDecision


def oracle_tier(outcomes: Mapping[str, bool], model_order: Sequence[str]) -> int:
    """Cost-optimal tier: cheapest correct model, or tier 0 when no model is correct."""
    tier = cheapest_correct_tier(outcomes, model_order)
    return 0 if tier == len(model_order) else tier


class OracleRouter(BaseRouter):
    name = "oracle"
    deployable = False

    def __init__(self, pool: ModelPool):
        super().__init__(pool)
        self.outcomes: Mapping[str, Mapping[str, bool]] = {}

    def set_outcomes(self, outcomes: Mapping[str, Mapping[str, bool]]) -> None:
        self.outcomes = outcomes

    def route(
        self,
        query: Query,
        analysis: QueryAnalysis,
        difficulty: DifficultyEstimate,
        ctx: CallContext,
    ) -> RoutingDecision:
        if query.id not in self.outcomes:
            raise KeyError(f"Oracle router has no outcomes for query '{query.id}'")
        tier = oracle_tier(self.outcomes[query.id], self.pool.names)
        return RoutingDecision(
            self.pool.by_tier(tier), self.name, reason=f"oracle tier {tier} (NOT DEPLOYABLE)"
        )
