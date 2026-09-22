"""Router interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from routeguard.complexity.base import TrainingExample
from routeguard.context import CallContext
from routeguard.models.pool import ModelPool
from routeguard.types import DifficultyEstimate, Query, QueryAnalysis, RoutingDecision


class BaseRouter(ABC):
    """Chooses one model from the pool for a query, *before* any generation.

    Routers only see the query, its analysis (detected language, predicted
    category, features) and the difficulty estimate. Deployable routers never
    see gold labels; :class:`~routeguard.router.oracle.OracleRouter` is the
    single, clearly-marked exception used for upper-bound analysis.
    """

    name: str = "base"
    requires_fit: bool = False
    deployable: bool = True

    def __init__(self, pool: ModelPool):
        self.pool = pool

    def fit(self, examples: Sequence[TrainingExample]) -> None:  # noqa: B027 - optional hook
        """Fit on training-split examples (no-op for unsupervised routers)."""

    @abstractmethod
    def route(
        self,
        query: Query,
        analysis: QueryAnalysis,
        difficulty: DifficultyEstimate,
        ctx: CallContext,
    ) -> RoutingDecision: ...
