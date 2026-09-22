"""Escalation policy: when is an attempt unreliable, and what happens next.

An attempt is **unreliable** if any enabled trigger fires:

* ``low_confidence``      – confidence below the acceptance threshold. The
  threshold is either fixed (``confidence_below``) or chosen per model on the
  calibration split with risk control (``risk_control``), see
  :mod:`routeguard.confidence.selective`;
* ``verification_failed`` – an applicable verifier rejected the answer;
* ``high_difficulty``     – the *initial* attempt came from a non-strongest model
  although the difficulty estimate exceeds ``difficulty_above``.

Unreliable attempts trigger the configured stages in order until an attempt is
reliable or ``max_stages`` stages have run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from routeguard.confidence.selective import ThresholdResult
from routeguard.config import EscalationConfig
from routeguard.types import Attempt, DifficultyEstimate


@dataclass
class EscalationPolicy:
    config: EscalationConfig
    strongest_model: str
    thresholds: dict[str, ThresholdResult] = field(default_factory=dict)
    initial_thresholds: dict[str, ThresholdResult] = field(default_factory=dict)

    def threshold_for(self, model: str, initial: bool = False) -> float | None:
        if self.config.triggers.risk_control is not None:
            if initial and model in self.initial_thresholds:
                return self.initial_thresholds[model].threshold
            if model in self.thresholds:
                return self.thresholds[model].threshold
        return self.config.triggers.confidence_below

    def triggers(
        self, attempt: Attempt, difficulty: DifficultyEstimate | None, initial: bool
    ) -> list[str]:
        t = self.config.triggers
        fired: list[str] = []
        threshold = self.threshold_for(attempt.model, initial)
        if (
            threshold is not None
            and attempt.confidence is not None
            and attempt.confidence.value < threshold
        ):
            fired.append("low_confidence")
        if (
            t.on_verification_failure
            and attempt.verification is not None
            and attempt.verification.passed is False
        ):
            fired.append("verification_failed")
        if (
            initial
            and t.difficulty_above is not None
            and difficulty is not None
            and difficulty.score > t.difficulty_above
            and attempt.model != self.strongest_model
        ):
            fired.append("high_difficulty")
        return fired

    def select_final(self, attempts: list[Attempt]) -> Attempt:
        """Pick the answer to return when no attempt was judged reliable."""
        reliable = [a for a in attempts if a.reliable]
        if reliable:
            return reliable[-1]
        if self.config.final_selection == "most_confident":
            scored = [a for a in attempts if a.confidence is not None and a.answer is not None]
            if scored:
                return max(scored, key=lambda a: a.confidence.value if a.confidence else 0.0)
        answered = [a for a in attempts if a.answer is not None]
        return answered[-1] if answered else attempts[-1]
