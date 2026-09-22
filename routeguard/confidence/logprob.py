"""Single-pass confidence from token log-probabilities (no extra generation cost).

If a backend does not return log-probabilities the estimators raise instead of
returning a made-up value; configure a sampling-based estimator for such backends.
"""

from __future__ import annotations

import math

from routeguard.confidence.base import BaseConfidenceEstimator, ConfidenceInput
from routeguard.context import CallContext


class MissingLogprobsError(RuntimeError):
    pass


def _logprobs(inp: ConfidenceInput) -> list[float]:
    lps = inp.output.token_logprobs
    if not lps:
        raise MissingLogprobsError(
            f"Model '{inp.model}' returned no token log-probabilities; use a sampling-based "
            "confidence method (self_consistency / semantic_entropy) for this backend."
        )
    return lps


class MeanTokenProb(BaseConfidenceEstimator):
    """Arithmetic mean of generated-token probabilities."""

    name = "mean_token_prob"

    def score(self, inp: ConfidenceInput, ctx: CallContext) -> tuple[float, dict]:
        lps = _logprobs(inp)
        return sum(math.exp(lp) for lp in lps) / len(lps), {"n_tokens": len(lps)}


class SequenceLogProb(BaseConfidenceEstimator):
    """Length-normalised sequence probability, ``exp(mean log p)`` (geometric mean)."""

    name = "sequence_logprob"

    def score(self, inp: ConfidenceInput, ctx: CallContext) -> tuple[float, dict]:
        lps = _logprobs(inp)
        total = sum(lps)
        return math.exp(total / len(lps)), {"sum_logprob": total, "n_tokens": len(lps)}


class MinTokenProb(BaseConfidenceEstimator):
    """Probability of the least likely generated token ("weakest link")."""

    name = "min_token_prob"

    def score(self, inp: ConfidenceInput, ctx: CallContext) -> tuple[float, dict]:
        return math.exp(min(_logprobs(inp))), {}


class TokenEntropy(BaseConfidenceEstimator):
    """``1 - mean normalised entropy`` of the top-k next-token distributions.

    Entropy is computed over the renormalised top-k probabilities, so it is an
    approximation of the full-vocabulary entropy (k is typically 5).
    """

    name = "entropy"

    def score(self, inp: ConfidenceInput, ctx: CallContext) -> tuple[float, dict]:
        tops = inp.output.top_logprobs
        if not tops:
            raise MissingLogprobsError(f"Model '{inp.model}' returned no top-k log-probabilities")
        norm_entropies = []
        for step in tops:
            probs = [math.exp(lp) for lp in step]
            z = sum(probs)
            if len(probs) < 2 or z <= 0:
                norm_entropies.append(0.0)
                continue
            h = -sum((p / z) * math.log(p / z) for p in probs if p > 0)
            norm_entropies.append(h / math.log(len(probs)))
        mean_h = sum(norm_entropies) / len(norm_entropies)
        return 1.0 - mean_h, {"mean_normalized_entropy": mean_h}
