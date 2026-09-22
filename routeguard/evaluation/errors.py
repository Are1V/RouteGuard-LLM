"""Automatic failure analysis.

Every record receives zero or more failure labels. Labels are *diagnostic*: they
are derived from observable signals (per-model outcomes, confidence, verifier
verdicts, escalation trace, parallel items) and are meant to direct manual
inspection, not to replace it. Definitions are listed in :data:`TAXONOMY` and in
docs/research_methodology.md.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Any

Record = dict[str, Any]

TAXONOMY: dict[str, str] = {
    "incorrect_routing": "final answer wrong; the routed model was wrong but a stronger model was "
    "right, and escalation did not recover",
    "model_capability_failure": "no model in the pool answered correctly "
    "(reasoning/knowledge limit)",
    "extraction_failure": "no answer could be parsed from the final response",
    "high_confidence_wrong": "initial answer wrong, its confidence was above the acceptance "
    "threshold, and the verifier did not reject it",
    "low_confidence_correct": "initial answer correct but flagged as low-confidence "
    "(unnecessary escalation)",
    "verifier_false_pass": "a verifier accepted a wrong final answer",
    "verifier_false_fail": "a verifier rejected a correct initial answer",
    "escalation_failure": "escalated, still wrong, although some model in the pool was correct",
    "escalation_harm": "initial answer correct, final answer wrong after escalation",
    "language_related_failure": "wrong in a non-English language while the English parallel item "
    "was answered correctly by the same system and seed",
    "retrieval_failure": "retrieval stage ran but no retrieved passage contained the gold answer",
    "unsupported_answer": "answer produced after retrieval failed (answer without evidence)",
}


def _english_outcomes(records: Sequence[Record]) -> dict[tuple[str, int, str], bool]:
    table = {}
    for r in records:
        if r["language"] == "en" and r.get("parallel_id"):
            table[(r["system"], r["seed"], r["parallel_id"])] = r["correct"]
    return table


def label_record(r: Record, english: dict[tuple[str, int, str], bool]) -> list[str]:
    labels: list[str] = []
    first = r["attempts"][0]
    final = r["attempts"][-1] if r["attempts"] else first
    outcomes = r.get("model_outcomes")
    any_correct = r.get("any_model_correct")

    if first["correct"] and "low_confidence" in (first["triggers"] or []):
        labels.append("low_confidence_correct")
    if first["correct"] and first["verified"] is False:
        labels.append("verifier_false_fail")
    if r["escalated"] and r["initial_correct"] and not r["correct"]:
        labels.append("escalation_harm")

    retrieval = [a for a in r["attempts"] if a["stage"] == "retrieval"]
    if retrieval and r.get("gold") is not None:
        # Retrieval quality is judged from the retrieval stage's own diagnostics.
        info = retrieval[-1]["info"] or {}
        if info.get("gold_in_evidence") is False:
            labels.append("retrieval_failure")
            if retrieval[-1]["answer"] is not None and not retrieval[-1]["correct"]:
                labels.append("unsupported_answer")

    if r["correct"]:
        return labels

    if r["extraction_failed"]:
        labels.append("extraction_failure")
    if outcomes is not None:
        if not any_correct:
            labels.append("model_capability_failure")
        else:
            routed_model = r["model_order"][r["routed_tier"]]
            stronger_ok = any(outcomes[m] for m in r["model_order"][r["routed_tier"] + 1 :])
            if not outcomes[routed_model] and stronger_ok and not r["escalated"]:
                labels.append("incorrect_routing")
            if r["escalated"]:
                labels.append("escalation_failure")
    if (
        not first["correct"]
        and not r["escalated"]
        and first["confidence"] is not None
        and "low_confidence" not in (first["triggers"] or [])
        and first["verified"] is not False
    ):
        labels.append("high_confidence_wrong")
    if final["verified"] is True:
        labels.append("verifier_false_pass")
    key = (r["system"], r["seed"], r.get("parallel_id") or "")
    if r["language"] != "en" and english.get(key) is True:
        labels.append("language_related_failure")
    return labels


def analyze_errors(records: Sequence[Record]) -> dict[str, Any]:
    english = _english_outcomes(records)
    per_system: dict[str, Counter[str]] = defaultdict(Counter)
    per_language: dict[str, Counter[str]] = defaultdict(Counter)
    totals: Counter[str] = Counter()
    wrong: Counter[str] = Counter()
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        labels = label_record(r, english)
        r["failure_labels"] = labels
        totals[r["system"]] += 1
        wrong[r["system"]] += int(not r["correct"])
        for lab in labels:
            per_system[r["system"]][lab] += 1
            per_language[r["language_variant"]][lab] += 1
            if len(examples[lab]) < 5:
                examples[lab].append(
                    {
                        "system": r["system"],
                        "item_id": r["item_id"],
                        "language": r["language_variant"],
                        "gold": r.get("gold"),
                        "final_answer": r["final_answer"],
                    }
                )
    return {
        "taxonomy": TAXONOMY,
        "per_system": {s: dict(c) for s, c in per_system.items()},
        "per_language": {lang: dict(c) for lang, c in per_language.items()},
        "n_records": dict(totals),
        "n_wrong": dict(wrong),
        "examples": dict(examples),
    }
