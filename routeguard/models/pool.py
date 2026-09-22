"""Model registry and the ordered model pool used by routers and escalation."""

from __future__ import annotations

import itertools
import logging
from collections.abc import Callable, Iterator

from routeguard.models.base import BaseLLM, ModelSpec
from routeguard.models.cache import CachedLLM, GenerationCache

logger = logging.getLogger(__name__)

BackendLoader = Callable[[], type[BaseLLM]]
_BACKENDS: dict[str, BackendLoader] = {}


def register_backend(name: str, loader: BackendLoader) -> None:
    """Register a backend by a zero-argument function returning its class.

    The indirection keeps heavy imports (torch, transformers) out of ``import routeguard``.
    """
    _BACKENDS[name] = loader


def available_backends() -> list[str]:
    return sorted(_BACKENDS)


def backend_class(backend: str) -> type[BaseLLM]:
    if backend not in _BACKENDS:
        raise ValueError(f"Unknown backend '{backend}'. Available: {available_backends()}")
    return _BACKENDS[backend]()


def build_llm(spec: ModelSpec) -> BaseLLM:
    return backend_class(spec.backend)(spec)


def _simulated() -> type[BaseLLM]:
    from routeguard.models.simulated import SimulatedLLM

    return SimulatedLLM


def _huggingface() -> type[BaseLLM]:
    from routeguard.models.huggingface import HuggingFaceLLM

    return HuggingFaceLLM


def _openai_compatible() -> type[BaseLLM]:
    from routeguard.models.openai_compat import OpenAICompatibleLLM

    return OpenAICompatibleLLM


register_backend("simulated", _simulated)
register_backend("huggingface", _huggingface)
register_backend("openai_compatible", _openai_compatible)


class ModelPool:
    """Models ordered from weakest/cheapest (tier 0) to strongest/most expensive.

    The order is taken from the configuration, which keeps the semantics explicit
    (a cheaper model is not always a weaker one). A warning is logged if the
    configured order disagrees with the estimated relative cost.

    Models are instantiated lazily, so a system that never routes to the large
    model never loads it.
    """

    def __init__(self, specs: list[ModelSpec], cache: GenerationCache | None = None):
        if not specs:
            raise ValueError("The model pool needs at least one model")
        names = [s.name for s in specs]
        if len(set(names)) != len(names):
            raise ValueError(f"Duplicate model names in pool: {names}")
        self.specs = specs
        self.cache = cache
        self._instances: dict[str, BaseLLM] = {}
        costs = [s.relative_cost() for s in specs]
        if any(b < a for a, b in itertools.pairwise(costs)):
            logger.warning("Model order %s is not monotone in estimated cost %s", names, costs)

    def __iter__(self) -> Iterator[ModelSpec]:
        return iter(self.specs)

    def __len__(self) -> int:
        return len(self.specs)

    @property
    def names(self) -> list[str]:
        return [s.name for s in self.specs]

    def spec(self, name: str) -> ModelSpec:
        for s in self.specs:
            if s.name == name:
                return s
        raise KeyError(f"Model '{name}' is not in the pool {self.names}")

    def tier(self, name: str) -> int:
        return self.names.index(name)

    def by_tier(self, tier: int) -> str:
        return self.names[max(0, min(tier, len(self.specs) - 1))]

    @property
    def cheapest(self) -> str:
        return self.names[0]

    @property
    def strongest(self) -> str:
        return self.names[-1]

    def next_stronger(self, name: str) -> str | None:
        t = self.tier(name)
        return self.names[t + 1] if t + 1 < len(self.specs) else None

    def normalized_costs(self) -> dict[str, float]:
        costs = {s.name: s.relative_cost() for s in self.specs}
        top = max(costs.values()) or 1.0
        return {k: v / top for k, v in costs.items()}

    def get(self, name: str) -> BaseLLM:
        if name not in self._instances:
            spec = self.spec(name)
            if self.cache is not None:
                self._instances[name] = CachedLLM(spec, backend_class(spec.backend), self.cache)
            else:
                self._instances[name] = build_llm(spec)
        return self._instances[name]

    def requires_reference(self, name: str) -> bool:
        """Class-level check; never instantiates (or loads) the backend."""
        return backend_class(self.spec(name).backend).requires_reference

    @property
    def simulated(self) -> bool:
        return any(s.backend == "simulated" for s in self.specs)

    def resource_stats(self) -> dict[str, dict[str, object]]:
        return {name: llm.resource_stats() for name, llm in self._instances.items()}
