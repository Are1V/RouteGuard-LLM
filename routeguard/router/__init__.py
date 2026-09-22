"""Routing strategies."""

from __future__ import annotations

from typing import Any

from routeguard.models.pool import ModelPool
from routeguard.router.base import BaseRouter
from routeguard.router.learned import CostAwareRouter, LearnedRouter, QualityCostRouter
from routeguard.router.oracle import OracleRouter
from routeguard.router.simple import FixedRouter, RandomRouter, RuleRouter, ThresholdRouter

ROUTERS: dict[str, type[BaseRouter]] = {
    "fixed": FixedRouter,
    "random": RandomRouter,
    "rules": RuleRouter,
    "threshold": ThresholdRouter,
    "learned": LearnedRouter,
    "cost_aware": CostAwareRouter,
    "quality_cost": QualityCostRouter,
    "oracle": OracleRouter,
}
_SEEDED = {"random", "learned", "cost_aware", "quality_cost"}


def build_router(kind: str, pool: ModelPool, options: dict[str, Any], seed: int = 0) -> BaseRouter:
    if kind not in ROUTERS:
        raise ValueError(f"Unknown router '{kind}'. Available: {sorted(ROUTERS)}")
    kwargs = dict(options)
    if kind in _SEEDED:
        kwargs.setdefault("seed", seed)
    return ROUTERS[kind](pool, **kwargs)


__all__ = ["ROUTERS", "BaseRouter", "OracleRouter", "build_router"]
