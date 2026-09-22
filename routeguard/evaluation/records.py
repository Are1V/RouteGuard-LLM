"""Per-example evaluation records.

A record joins a :class:`~routeguard.types.PipelineResult` with the gold item,
the deterministic scores of the initial and final answers, and the per-model
outcomes on the same item (for routing analysis and the oracle). Records are
written verbatim to ``raw/*.jsonl`` so that every metric can be recomputed later
with ``routeguard evaluate`` without re-running any model.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import Any

from routeguard.benchmarks.schema import Item
from routeguard.config import ScoringConfig
from routeguard.evaluation.scoring import Score, score_prediction
from routeguard.router.oracle import oracle_tier
from routeguard.types import Attempt, PipelineResult
from routeguard.utils.text import normalize_text


def score_item(prediction: str | None, item: Item, scoring: ScoringConfig) -> Score:
    return score_prediction(
        prediction,
        item.answer,
        item.answer_type,
        text_match=scoring.text_match,
        f1_threshold=scoring.f1_threshold,
        eval_tests=item.eval_tests,
        timeout_s=scoring.code_timeout_s,
    )


def _attempt_summary(a: Attempt, correct: bool | None) -> dict[str, Any]:
    return {
        "stage": a.stage,
        "model": a.model,
        "answer": a.answer,
        "correct": correct,
        "confidence_raw": a.confidence.raw if a.confidence else None,
        "confidence": a.confidence.value if a.confidence else None,
        "calibrated": a.confidence.calibrated is not None if a.confidence else False,
        "verified": a.verification.passed if a.verification else None,
        "verifier": a.verification.verifier if a.verification else None,
        "verification_reason": a.verification.reason if a.verification else "",
        "reliable": a.reliable,
        "triggers": a.trigger,
        "info": a.info,
    }


def annotate_retrieval(attempt: dict[str, Any], item: Item, doc_text: Callable[[str], str]) -> None:
    """Evaluation-time retrieval diagnostics (uses gold data, so never done in the pipeline).

    ``gold_in_evidence``: a normalised gold alias occurs in a retrieved passage.
    ``gold_doc_recall``: fraction of ``item.metadata['gold_doc_ids']`` retrieved, if annotated.
    """
    retrieved = attempt["info"].get("retrieved")
    if retrieved is None or item.answer_type.value == "code":
        return
    ids = [d["id"] for d in retrieved]
    texts = [normalize_text(doc_text(i)) for i in ids]
    golds = item.answer if isinstance(item.answer, list) else [item.answer]
    if item.answer_type.value == "choice" and item.choices:
        golds = [item.choices["ABCDEFGHIJ".index(g)] for g in golds]
    attempt["info"]["gold_in_evidence"] = any(
        normalize_text(str(g)) and normalize_text(str(g)) in t for g in golds for t in texts
    )
    gold_ids = item.metadata.get("gold_doc_ids")
    if gold_ids:
        attempt["info"]["gold_doc_recall"] = len(set(gold_ids) & set(ids)) / len(set(gold_ids))


def build_record(
    result: PipelineResult,
    item: Item,
    scoring: ScoringConfig,
    seed: int,
    model_order: list[str],
    model_outcomes: dict[str, bool] | None,
    score_cache: dict[tuple[str, str | None], Score] | None = None,
    doc_text: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Score every attempt (cached per answer string) and flatten the trace."""
    cache = score_cache if score_cache is not None else {}

    def score(ans: str | None) -> Score:
        key = (item.id, ans)
        if key not in cache:
            cache[key] = score_item(ans, item, scoring)
        return cache[key]

    attempt_scores = [score(a.answer) for a in result.attempts]
    initial, final = attempt_scores[0], attempt_scores[result.final_index]
    totals = result.totals()
    overhead = result.escalation_overhead()
    purposes = Counter(c.purpose for c in result.calls)
    n_models = len(model_order)
    record: dict[str, Any] = {
        "system": result.system,
        "seed": seed,
        "item_id": item.id,
        "source": item.source,
        "language": item.language,
        "language_variant": item.language_variant or item.language,
        "category": item.category,
        "answer_type": item.answer_type.value,
        "parallel_id": item.parallel_id,
        "gold": item.answer if item.answer_type.value != "code" else None,
        "detected_language": result.analysis.language,
        "language_confidence": result.analysis.language_confidence,
        "predicted_category": result.analysis.category,
        "difficulty_score": result.difficulty.score,
        "difficulty_label": result.difficulty.label.value,
        "model_order": list(model_order),
        "routed_model": result.routing.model,
        "routed_tier": model_order.index(result.routing.model),
        "routing_reason": result.routing.reason,
        "initial_answer": result.initial.answer,
        "initial_correct": initial.correct,
        "final_answer": result.final_answer,
        "final_model": result.final_model,
        "final_tier": model_order.index(result.final_model),
        "correct": final.correct,
        "exact_match": final.exact_match,
        "f1": final.f1,
        "extraction_failed": final.extraction_failed,
        "escalated": result.escalated,
        "escalation_causes": result.escalation_causes,
        "n_stages": len(result.attempts) - 1,
        "stages": [a.stage for a in result.attempts[1:]],
        "attempts": [
            _attempt_summary(a, s.correct)
            for a, s in zip(result.attempts, attempt_scores, strict=True)
        ],
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "latency_s": totals["latency_s"],
        "cost_usd": totals["cost_usd"],
        "tflops": totals["tflops"],
        "n_calls": totals["n_calls"],
        "escalation_cost_usd": overhead["cost_usd"],
        "escalation_tflops": overhead["tflops"],
        "escalation_latency_s": overhead["latency_s"],
        "escalation_tokens": overhead["input_tokens"] + overhead["output_tokens"],
        "calls_by_purpose": dict(purposes),
        "cached_calls": sum(c.cached for c in result.calls),
    }
    if doc_text is not None:
        for a in record["attempts"]:
            annotate_retrieval(a, item, doc_text)
    if model_outcomes is not None:
        record["model_outcomes"] = model_outcomes
        record["oracle_tier"] = oracle_tier(model_outcomes, model_order)
        record["any_model_correct"] = any(model_outcomes.values())
        record["n_models"] = n_models
    return record
