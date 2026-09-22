"""Escalation stages.

A stage receives the attempts made so far and produces a new candidate
:class:`~routeguard.types.Attempt` (or ``None`` if it cannot apply, e.g. the
``stronger_model`` stage when the strongest model already answered). Stages
generate through the pipeline so that confidence estimation, verification, and
cost accounting are identical to the initial attempt.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from typing import TYPE_CHECKING, Any

from routeguard.answers import extract_answer
from routeguard.confidence.consistency import cluster_answers
from routeguard.prompts import build_messages, judge_select_messages
from routeguard.types import Attempt, ConfidenceResult, QueryAnalysis

if TYPE_CHECKING:
    from routeguard.context import CallContext
    from routeguard.pipeline import RouteGuardPipeline
    from routeguard.types import Query


class EscalationStage(ABC):
    name: str = "stage"

    def __init__(self, **options: Any):
        if options:
            raise ValueError(
                f"Unknown options for escalation stage '{self.name}': {sorted(options)}"
            )

    @abstractmethod
    def run(
        self,
        pipe: RouteGuardPipeline,
        query: Query,
        analysis: QueryAnalysis,
        attempts: list[Attempt],
        ctx: CallContext,
    ) -> Attempt | None: ...


class RepromptStage(EscalationStage):
    """Stage 1: same model, stronger ("careful") prompt."""

    name = "reprompt"

    def run(
        self,
        pipe: RouteGuardPipeline,
        query: Query,
        analysis: QueryAnalysis,
        attempts: list[Attempt],
        ctx: CallContext,
    ) -> Attempt | None:
        return pipe.attempt(
            query, analysis, attempts[-1].model, ctx, stage=self.name, strategy="careful"
        )


class StrongerModelStage(EscalationStage):
    """Stage 2: next stronger model in the pool (or jump straight to the strongest)."""

    name = "stronger_model"

    def __init__(self, target: str = "next"):
        if target not in {"next", "strongest"}:
            raise ValueError("stronger_model.target must be 'next' or 'strongest'")
        self.target = target

    def run(
        self,
        pipe: RouteGuardPipeline,
        query: Query,
        analysis: QueryAnalysis,
        attempts: list[Attempt],
        ctx: CallContext,
    ) -> Attempt | None:
        current = max(attempts, key=lambda a: pipe.pool.tier(a.model)).model
        model = (
            pipe.pool.strongest if self.target == "strongest" else pipe.pool.next_stronger(current)
        )
        if model is None or pipe.pool.tier(model) <= pipe.pool.tier(current):
            return None
        return pipe.attempt(query, analysis, model, ctx, stage=self.name)


class RetrievalStage(EscalationStage):
    """Stage 3: add BM25 evidence from the configured corpus and re-answer."""

    name = "retrieval"

    def __init__(self, k: int | None = None, model: str = "current", same_language: bool = False):
        self.k = k
        self.model = model
        self.same_language = same_language

    def run(
        self,
        pipe: RouteGuardPipeline,
        query: Query,
        analysis: QueryAnalysis,
        attempts: list[Attempt],
        ctx: CallContext,
    ) -> Attempt | None:
        if pipe.retriever is None:
            raise RuntimeError("retrieval stage configured without a retriever")
        k = self.k or (pipe.config.retrieval.k if pipe.config.retrieval else 3)
        lang = analysis.language if self.same_language else None
        hits = pipe.retriever.search(query.text, k=k, language=lang)
        evidence = [h.doc.text for h in hits]
        model = attempts[-1].model if self.model == "current" else self.model
        attempt = pipe.attempt(query, analysis, model, ctx, stage=self.name, evidence=evidence)
        attempt.info["retrieved"] = [{"id": h.doc.id, "score": round(h.score, 3)} for h in hits]
        return attempt


class SelfConsistencyStage(EscalationStage):
    """Stage 4: sample several answers and take the majority vote.

    The vote share is reported as a *raw* confidence; it is not calibrated.
    """

    name = "self_consistency"

    def __init__(self, n: int = 5, temperature: float = 0.7, model: str = "current"):
        self.n = n
        self.temperature = temperature
        self.model = model

    def run(
        self,
        pipe: RouteGuardPipeline,
        query: Query,
        analysis: QueryAnalysis,
        attempts: list[Attempt],
        ctx: CallContext,
    ) -> Attempt | None:
        model = attempts[-1].model if self.model == "current" else self.model
        messages = build_messages(query, analysis.category)
        outs = ctx.generate_samples(
            model,
            messages,
            purpose="escalation_self_consistency",
            n=self.n,
            temperature=self.temperature,
        )
        answers = [extract_answer(o.text, query.answer_type, query.choices) for o in outs]
        labels = cluster_answers(answers, query.answer_type)
        votes = Counter(lab for lab, a in zip(labels, answers, strict=True) if a is not None)
        if not votes:
            best_idx = 0
            share = 0.0
        else:
            best_label, count = votes.most_common(1)[0]
            best_idx = labels.index(best_label)
            share = count / len(answers)
        confidence = ConfidenceResult(raw=share, method="vote_share", details={"answers": answers})
        return pipe.finalize_attempt(
            query,
            analysis,
            model,
            outs[best_idx],
            answers[best_idx],
            ctx,
            stage=self.name,
            confidence=confidence,
        )


class JudgeSelectStage(EscalationStage):
    """Stage 5: a (stronger) model adjudicates between previous candidate answers."""

    name = "judge_select"

    def __init__(self, model: str = "strongest"):
        self.model = model

    def run(
        self,
        pipe: RouteGuardPipeline,
        query: Query,
        analysis: QueryAnalysis,
        attempts: list[Attempt],
        ctx: CallContext,
    ) -> Attempt | None:
        model = pipe.pool.strongest if self.model == "strongest" else self.model
        candidates = [a.answer for a in attempts if a.answer is not None]
        if not candidates:
            return pipe.attempt(query, analysis, model, ctx, stage=self.name)
        messages = judge_select_messages(query, list(dict.fromkeys(candidates)))
        out = ctx.generate(model, messages, purpose="escalation_judge_select")
        answer = extract_answer(out.text, query.answer_type, query.choices)
        return pipe.finalize_attempt(
            query, analysis, model, out, answer, ctx, stage=self.name, messages=messages
        )


class ToolStage(EscalationStage):
    """Re-answer numeric questions with a calculator / unit-converter tool loop."""

    name = "tool"

    def __init__(self, model: str = "current", tools: list[str] | None = None, max_steps: int = 3):
        from routeguard.tools.base import BUILTIN_TOOLS

        names = tools or ["calculator", "unit_convert"]
        unknown = set(names) - set(BUILTIN_TOOLS)
        if unknown:
            raise ValueError(f"Unknown tools {sorted(unknown)}; available: {sorted(BUILTIN_TOOLS)}")
        self.model = model
        self.tools = [BUILTIN_TOOLS[n] for n in names]
        self.max_steps = max_steps

    def run(
        self,
        pipe: RouteGuardPipeline,
        query: Query,
        analysis: QueryAnalysis,
        attempts: list[Attempt],
        ctx: CallContext,
    ) -> Attempt | None:
        from routeguard.tools.agent import ToolAgent
        from routeguard.types import AnswerType

        if query.answer_type != AnswerType.NUMERIC:
            return None
        model = attempts[-1].model if self.model == "current" else self.model
        trace = ToolAgent(self.tools, self.max_steps).run(query, model, ctx)
        answer = extract_answer(trace.final_text, query.answer_type, query.choices)
        attempt = pipe.finalize_attempt(
            query, analysis, model, trace.last_output, answer, ctx, stage=self.name
        )
        attempt.info["tool_calls"] = [
            {"name": c.name, "arguments": c.arguments, "result": c.result, "error": c.error}
            for c in trace.calls
        ]
        return attempt


STAGES: dict[str, type[EscalationStage]] = {
    "reprompt": RepromptStage,
    "stronger_model": StrongerModelStage,
    "retrieval": RetrievalStage,
    "self_consistency": SelfConsistencyStage,
    "judge_select": JudgeSelectStage,
    "tool": ToolStage,
}


def register_stage(name: str, cls: type[EscalationStage]) -> None:
    STAGES[name] = cls


def build_stage(kind: str, options: dict[str, Any]) -> EscalationStage:
    if kind not in STAGES:
        raise ValueError(f"Unknown escalation stage '{kind}'. Available: {sorted(STAGES)}")
    return STAGES[kind](**options)
