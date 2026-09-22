"""Confidence-estimator interface.

An estimator returns a *raw* score in which larger means "more likely correct".
Raw scores are **not probabilities of correctness**: token probabilities of an
LLM are known to be miscalibrated, and consistency rates depend on the sampling
temperature. A separate calibrator (``routeguard.confidence.calibration``),
fitted on a held-out calibration split, maps raw scores to an estimate of the
empirical probability that the answer is correct.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from routeguard.context import CallContext
from routeguard.types import AnswerType, GenerationOutput, Message, Query


@dataclass
class ConfidenceInput:
    """Everything an estimator may use about one attempt."""

    query: Query
    model: str
    messages: list[Message]
    output: GenerationOutput
    answer: str | None
    answer_type: AnswerType


class BaseConfidenceEstimator(ABC):
    name: str = "base"

    @abstractmethod
    def score(self, inp: ConfidenceInput, ctx: CallContext) -> tuple[float, dict]:
        """Return a raw confidence score and diagnostic details."""
