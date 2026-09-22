"""Reference-aware simulated backend for tests, CI, and pipeline debugging.

.. warning::
   Results produced with this backend are **not model results**. The simulator
   reads the gold answer passed in ``request.metadata['reference']`` and decides
   whether to answer correctly with a probability that depends on a configured
   ``capability``, a latent item difficulty, and optional language/category
   offsets. It exists so that routing, confidence, verification, escalation,
   metrics, and plotting code can be exercised end-to-end on a laptop without
   downloading models. Every run manifest records ``simulated: true`` and every
   figure produced from such a run is watermarked.

The simulator is deterministic given (model, prompt, sample seed).
"""

from __future__ import annotations

import math
import random
from typing import Any

from routeguard.answers import canonical_number
from routeguard.models.base import BaseLLM, ModelSpec
from routeguard.types import AnswerType, GenerationOutput, GenerationRequest
from routeguard.utils.seeding import derive_seed, stable_hash


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class SimulatedLLM(BaseLLM):
    requires_reference = True

    def __init__(self, spec: ModelSpec):
        super().__init__(spec)
        o = spec.options
        self.capability = float(o.get("capability", 0.5))
        self.sharpness = float(o.get("sharpness", 6.0))
        self.language_offsets: dict[str, float] = dict(o.get("language_offsets", {}))
        self.category_offsets: dict[str, float] = dict(o.get("category_offsets", {}))
        self.tokens_per_second = float(o.get("tokens_per_second", 50.0))
        self.overhead_s = float(o.get("overhead_s", 0.05))
        # How separable correct/incorrect answers are in token log-probabilities.
        self.logprob_separation = float(o.get("logprob_separation", 0.25))

    # ------------------------------------------------------------------ helpers
    def _rng(self, request: GenerationRequest) -> random.Random:
        # Depends only on what a real model would see (prompt, sampling seed), never on
        # request metadata such as the call purpose; otherwise cached and uncached runs
        # of the same request could differ.
        prompt_hash = stable_hash(request.messages)
        sample = request.seed if request.temperature > 0 else "greedy"
        return random.Random(derive_seed(self.spec.model_id, self.capability, prompt_hash, sample))

    @staticmethod
    def latent_difficulty(ref: dict[str, Any]) -> float:
        if "difficulty" in ref and ref["difficulty"] is not None:
            return float(ref["difficulty"])
        # Items without an annotated difficulty get a stable pseudo-random one.
        return random.Random(derive_seed("difficulty", ref.get("id", ""))).random()

    def p_correct(self, ref: dict[str, Any], strategy_bonus: float = 0.0) -> float:
        logit = self.sharpness * (self.capability - self.latent_difficulty(ref))
        logit += self.language_offsets.get(str(ref.get("language")), 0.0)
        logit += self.category_offsets.get(str(ref.get("category")), 0.0)
        return _sigmoid(logit + strategy_bonus)

    def _usage(self, request: GenerationRequest, n_out: int) -> tuple[int, float]:
        n_in = max(1, sum(len(m["content"]) for m in request.messages) // 4)
        return n_in, self.overhead_s + n_out / self.tokens_per_second

    def _logprobs(
        self, rng: random.Random, n: int, correct: bool, temperature: float
    ) -> tuple[list[float], list[list[float]]]:
        centre = -0.08 if correct else -0.08 - self.logprob_separation
        centre -= 0.1 * temperature
        token_lps, tops = [], []
        for _ in range(n):
            lp = min(-1e-4, rng.gauss(centre, 0.12))
            p = math.exp(lp)
            rest = max(1e-6, 1.0 - p)
            alts = [math.log(rest * w) for w in (0.6, 0.25, 0.1, 0.05)]
            token_lps.append(lp)
            tops.append([lp, *alts])
        return token_lps, tops

    # --------------------------------------------------------------- generation
    def generate(self, request: GenerationRequest) -> GenerationOutput:
        ref = request.metadata.get("reference")
        purpose = request.metadata.get("purpose", "answer")
        rng = self._rng(request)
        if not ref:
            text = (
                "[simulated backend] No reference answer is available for this query, so the "
                "simulator cannot produce a meaningful response.\nFinal answer: unknown"
            )
            return self._package(request, rng, text, correct=False, n_out=24)
        if purpose == "difficulty_judge":
            rating = min(10, max(1, round(1 + 9 * self.latent_difficulty(ref) + rng.gauss(0, 1.5))))
            return self._package(request, rng, str(rating), correct=True, n_out=2)
        if purpose == "verify_judge":
            truth = self._candidate_correct(ref, request.metadata.get("candidate_answer"))
            accurate = rng.random() < 0.6 + 0.35 * self.capability
            verdict = truth if accurate else not truth
            return self._package(
                request, rng, "Yes" if verdict else "No", correct=accurate, n_out=1
            )

        if purpose == "tool_agent":
            return self._tool_step(request, ref, rng)

        bonus = 0.0
        if request.metadata.get("strategy") == "careful":
            bonus += 0.4
        if self._evidence_helps(ref, request.metadata.get("evidence") or []):
            bonus += 1.5
        correct = rng.random() < self.p_correct(ref, bonus)
        answer_type = AnswerType(ref.get("answer_type", "text"))
        answer = self._answer(ref, answer_type, correct, rng)
        if answer_type == AnswerType.CODE:
            text = f"Here is the solution.\n```python\n{answer}\n```"
            n_out = 40 + answer.count("\n") * 8
        else:
            steps = rng.randint(1, 4) if answer_type == AnswerType.NUMERIC else 1
            reasoning = "\n".join(f"Step {i + 1}: [simulated reasoning]" for i in range(steps))
            text = f"{reasoning}\nFinal answer: {answer}"
            n_out = 12 + steps * rng.randint(12, 30)
        return self._package(request, rng, text, correct=correct, n_out=n_out)

    def _tool_step(
        self, request: GenerationRequest, ref: dict[str, Any], rng: random.Random
    ) -> GenerationOutput:
        """Simulated tool-agent behaviour covering every tool-use failure type."""
        import json

        step = int(request.metadata.get("tool_step", 0))
        results = [r for r in request.metadata.get("tool_results") or [] if r is not None]
        expected = list(ref.get("expected_calls") or [])
        skilled = rng.random() < self.p_correct(ref)
        gold = str(ref.get("answer"))
        if step == 0 and expected:
            if skilled:
                call = expected[0]
                payload = {"name": call["name"], "arguments": call["arguments"]}
                text = f"TOOL_CALL: {json.dumps(payload)}"
            else:
                text = rng.choice(
                    [
                        f"The calculator returned {gold}.\nFinal answer: {gold}",  # fabricated
                        # malformed arguments:
                        'TOOL_CALL: {"name": "calculator", "arguments": {"expr": "1+1"}}',
                        "I will estimate it.\nFinal answer: 0",  # missing call
                    ]
                )
            return self._package(request, rng, text, correct=skilled, n_out=30)
        if step == 0:  # no tool needed
            if skilled:
                return self._package(request, rng, f"Final answer: {gold}", correct=True, n_out=8)
            text = 'TOOL_CALL: {"name": "calculator", "arguments": {"expression": "2+2"}}'
            return self._package(request, rng, text, correct=False, n_out=20)
        last = results[-1] if results else gold
        answer = (
            last if skilled or rng.random() < 0.5 else (canonical_number(f"{last}") or "0") + "1"
        )
        return self._package(
            request, rng, f"Final answer: {answer}", correct=answer == last, n_out=10
        )

    def _package(
        self, request: GenerationRequest, rng: random.Random, text: str, correct: bool, n_out: int
    ) -> GenerationOutput:
        n_out = min(n_out, request.max_new_tokens)
        n_in, latency = self._usage(request, n_out)
        lps, tops = self._logprobs(rng, n_out, correct, request.temperature)
        return GenerationOutput(
            text=text,
            model=self.spec.name,
            input_tokens=n_in,
            output_tokens=n_out,
            latency_s=latency,
            token_logprobs=lps if request.logprobs else None,
            top_logprobs=tops if request.logprobs else None,
            extra={"simulated": True},
        )

    @staticmethod
    def _evidence_helps(ref: dict[str, Any], evidence: list[str]) -> bool:
        """Evidence helps if it contains the gold passage, or the gold answer text
        (option text for multiple choice; never a bare option letter)."""
        if not evidence:
            return False
        texts = [str(e).lower() for e in evidence]
        passage = str(ref.get("context") or "").lower()
        if passage and any(passage[:200] in t for t in texts):
            return True
        gold = ref.get("answer")
        golds = [str(g) for g in (gold if isinstance(gold, list) else [gold])]
        if ref.get("answer_type") == "choice" and ref.get("choices"):
            golds = [ref["choices"]["ABCDEFGHIJ".index(g)] for g in golds if g in "ABCDEFGHIJ"]
        return any(len(g) > 1 and g.lower() in t for g in golds for t in texts)

    @staticmethod
    def _candidate_correct(ref: dict[str, Any], candidate: str | None) -> bool:
        from routeguard.evaluation.scoring import score_prediction

        answer_type = AnswerType(ref.get("answer_type", "text"))
        if answer_type == AnswerType.CODE:
            return (
                candidate is not None and candidate.strip() == str(ref.get("solution", "")).strip()
            )
        return score_prediction(candidate, ref.get("answer"), answer_type).correct

    @staticmethod
    def _answer(
        ref: dict[str, Any], answer_type: AnswerType, correct: bool, rng: random.Random
    ) -> str:
        gold = ref.get("answer")
        gold_str = str(gold[0] if isinstance(gold, list) else gold)
        if correct:
            return (
                str(ref.get("solution", gold_str)) if answer_type == AnswerType.CODE else gold_str
            )
        # Wrong answers are drawn from a small, item-specific distractor set so that
        # independent wrong samples sometimes agree (as real models do).
        drng = random.Random(derive_seed("distractors", ref.get("id", ""), gold_str))
        if answer_type == AnswerType.NUMERIC:
            base = float(canonical_number(gold_str) or 0)
            options = [
                base + d
                for d in (
                    drng.choice([-2, -1, 1, 2]),
                    drng.choice([3, 5, 10]),
                    -drng.choice([3, 4, 6]),
                )
            ]
            value = rng.choices(options, weights=[0.6, 0.25, 0.15])[0]
            return canonical_number(str(value)) or "0"
        if answer_type == AnswerType.CHOICE:
            n = len(ref.get("choices") or "ABCD")
            others = [c for c in "ABCDEFGHIJ"[:n] if c != gold_str]
            drng.shuffle(others)
            return rng.choices(others, weights=[0.6, 0.3, 0.1][: len(others)])[0]
        if answer_type == AnswerType.CODE:
            entry = ref.get("entry_point") or "solution"
            return f"def {entry}(*args, **kwargs):\n    return None"
        return rng.choice(["unknown", f"not {gold_str}", "none of the above"])
