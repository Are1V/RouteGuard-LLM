"""Backend-agnostic LLM interface and cost model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from routeguard.types import GenerationOutput, GenerationRequest


@dataclass
class ModelSpec:
    """Declarative description of one model in the pool.

    ``params_b`` (billions of parameters) drives the FLOP-based compute estimate.
    Prices are optional; local models usually leave them at 0 and are compared by
    compute instead. API keys are never part of a spec: backends read them from
    the environment variable named in ``options['api_key_env']``.
    """

    name: str
    backend: str
    model_id: str
    params_b: float = 0.0
    price_input_per_1k: float = 0.0
    price_output_per_1k: float = 0.0
    max_new_tokens: int = 512
    options: dict[str, Any] = field(default_factory=dict)

    def cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self.price_input_per_1k + output_tokens * self.price_output_per_1k
        ) / 1000

    def tflops(self, input_tokens: int, output_tokens: int) -> float:
        """Forward-pass compute estimate: ~2 FLOPs per parameter per token (Kaplan et al., 2020)."""
        return 2.0 * self.params_b * 1e9 * (input_tokens + output_tokens) / 1e12

    def relative_cost(self, nominal_in: int = 400, nominal_out: int = 200) -> float:
        """Cost of a nominal request, used by cost-aware routers to compare models.

        Uses monetary price when any price is configured, otherwise compute.
        """
        if self.price_input_per_1k > 0 or self.price_output_per_1k > 0:
            return self.cost_usd(nominal_in, nominal_out)
        return self.tflops(nominal_in, nominal_out)


class BaseLLM(ABC):
    """A text-generation backend.

    Subclasses implement :meth:`generate`; batching backends should also override
    :meth:`generate_batch`. ``requires_reference`` must stay ``False`` for every
    real backend: only the simulator may read ``request.metadata['reference']``.
    """

    requires_reference: bool = False

    def __init__(self, spec: ModelSpec):
        self.spec = spec

    @property
    def name(self) -> str:
        return self.spec.name

    @classmethod
    def spec_identity(cls, spec: ModelSpec) -> dict[str, Any]:
        """Everything that affects outputs; used as part of the generation-cache key.

        A class-level function of the spec, so cache lookups never need to load a model.
        Override it if a backend has output-affecting settings outside ``spec.options``.
        """
        output_affecting = {
            k: v
            for k, v in spec.options.items()
            if k not in {"api_key_env", "timeout_s", "max_retries", "batch_size", "device_map"}
        }
        return {"backend": spec.backend, "model_id": spec.model_id, "options": output_affecting}

    def identity(self) -> dict[str, Any]:
        return self.spec_identity(self.spec)

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationOutput: ...

    def generate_batch(self, requests: Sequence[GenerationRequest]) -> list[GenerationOutput]:
        return [self.generate(r) for r in requests]

    def resource_stats(self) -> dict[str, Any]:
        """Backend-specific resource usage (e.g. peak GPU memory)."""
        return {}
