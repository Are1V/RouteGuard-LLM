"""Sampling-based confidence: self-consistency and (discrete) semantic entropy.

Both draw ``n_samples`` additional generations at ``temperature`` from the same
model and prompt. These extra calls are charged to the query's cost.

* ``self_consistency`` – fraction of samples whose answer agrees with the
  primary (greedy) answer (Wang et al., 2023, used here as a confidence signal).
* ``semantic_entropy`` – answers (primary + samples) are clustered into
  equivalence classes and the confidence is ``1 - H(clusters) / log(n)``. This is
  the discrete variant of semantic entropy (Farquhar et al., 2024). Equivalence is
  decided by answer normalisation for numeric/choice/code answers and by character
  n-gram similarity for free text; NLI-based equivalence is not implemented.
"""

from __future__ import annotations

import math

from routeguard.answers import answers_equivalent, extract_answer
from routeguard.confidence.base import BaseConfidenceEstimator, ConfidenceInput
from routeguard.context import CallContext
from routeguard.types import AnswerType
from routeguard.utils.text import char_ngrams, jaccard


def equivalent(
    a: str | None, b: str | None, answer_type: AnswerType, text_threshold: float = 0.6
) -> bool:
    if answers_equivalent(a, b, answer_type):
        return True
    if answer_type == AnswerType.TEXT and a and b:
        return jaccard(char_ngrams(a), char_ngrams(b)) >= text_threshold
    return False


def cluster_answers(
    answers: list[str | None], answer_type: AnswerType, text_threshold: float = 0.6
) -> list[int]:
    """Greedy clustering: each answer joins the first cluster whose representative matches.

    ``None`` (unparseable) answers each form their own cluster, which correctly
    increases the measured uncertainty.
    """
    reps: list[str | None] = []
    labels: list[int] = []
    for ans in answers:
        for k, rep in enumerate(reps):
            if ans is not None and equivalent(ans, rep, answer_type, text_threshold):
                labels.append(k)
                break
        else:
            reps.append(ans)
            labels.append(len(reps) - 1)
    return labels


class _Sampling(BaseConfidenceEstimator):
    def __init__(self, n_samples: int = 5, temperature: float = 0.7, text_threshold: float = 0.6):
        if n_samples < 1:
            raise ValueError("n_samples must be >= 1")
        self.n_samples = n_samples
        self.temperature = temperature
        self.text_threshold = text_threshold

    def samples(self, inp: ConfidenceInput, ctx: CallContext) -> list[str | None]:
        outs = ctx.generate_samples(
            inp.model,
            inp.messages,
            purpose="confidence_sample",
            n=self.n_samples,
            temperature=self.temperature,
        )
        return [extract_answer(o.text, inp.answer_type, inp.query.choices) for o in outs]


class SelfConsistency(_Sampling):
    name = "self_consistency"

    def score(self, inp: ConfidenceInput, ctx: CallContext) -> tuple[float, dict]:
        answers = self.samples(inp, ctx)
        agree = sum(
            equivalent(inp.answer, a, inp.answer_type, self.text_threshold) for a in answers
        )
        return agree / len(answers), {"samples": answers, "agree": agree}


class SemanticEntropy(_Sampling):
    name = "semantic_entropy"

    def score(self, inp: ConfidenceInput, ctx: CallContext) -> tuple[float, dict]:
        answers = [inp.answer, *self.samples(inp, ctx)]
        labels = cluster_answers(answers, inp.answer_type, self.text_threshold)
        n = len(labels)
        counts = [labels.count(k) for k in set(labels)]
        h = -sum((c / n) * math.log(c / n) for c in counts)
        return 1.0 - h / math.log(n), {
            "samples": answers[1:],
            "n_clusters": len(counts),
            "entropy": h,
        }
