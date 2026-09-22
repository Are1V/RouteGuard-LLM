"""Metrics, tables, figures, and the error-analysis report from raw records.

This module is the single path from per-example records to every reported
number: the benchmark runner calls it after an experiment, and
``routeguard evaluate`` / ``routeguard plot`` call it on saved records.
"""

from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from routeguard.evaluation import plots
from routeguard.evaluation.errors import TAXONOMY, analyze_errors
from routeguard.evaluation.metrics import (
    acceptance_metrics,
    quality_metrics,
    reliability_metrics,
    routing_confusion,
    system_metrics,
)
from routeguard.evaluation.stats import (
    aggregate_seeds,
    mcnemar_exact,
    mean_std,
    paired_bootstrap,
)
from routeguard.evaluation.tables import SIMULATED_NOTE, MeanStd, Table

logger = logging.getLogger(__name__)
Record = dict[str, Any]


@dataclass
class ReportMeta:
    model_order: list[str]
    system_groups: dict[str, str]
    simulated: bool = False
    reference_system: str | None = None
    figure_formats: list[str] = field(default_factory=lambda: ["png", "pdf"])
    cost_unit: str = "tflops"  # "usd" when any model has a price


def load_records(paths: Sequence[str | Path]) -> list[Record]:
    records: list[Record] = []
    for p in paths:
        with Path(p).open(encoding="utf-8") as f:
            records.extend(json.loads(line) for line in f if line.strip())
    return records


def _by(records: Sequence[Record], *keys: str) -> dict[tuple[Any, ...], list[Record]]:
    out: dict[tuple[Any, ...], list[Record]] = defaultdict(list)
    for r in records:
        out[tuple(r[k] for k in keys)].append(r)
    return out


def fixed_model_of(records: Sequence[Record]) -> str | None:
    """The model a system always uses, if it never routes elsewhere and never escalates."""
    models = {r["routed_model"] for r in records}
    if len(models) == 1 and not any(r["escalated"] for r in records):
        return next(iter(models))
    return None


def mixture_frontier(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Upper concave hull of (cost, accuracy) points of fixed-model systems.

    Randomly sending a fraction of queries to each fixed model achieves any convex
    combination of their (cost, accuracy), so this hull is what a router must beat to add
    value beyond *how much* compute it spends.
    """
    hull: list[tuple[float, float]] = []
    for p in sorted(set(points)):
        while len(hull) >= 2:
            (x1, y1), (x2, y2) = hull[-2], hull[-1]
            if (x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1) >= 0:
                hull.pop()
            else:
                break
        hull.append(p)
    # keep only the non-decreasing part (spending more should never be forced to lose accuracy)
    frontier = [hull[0]]
    for p in hull[1:]:
        if p[1] >= frontier[-1][1]:
            frontier.append(p)
    return frontier


def mixture_gaps(summary: dict[str, Any], cost_key: str) -> dict[str, dict[str, float]]:
    """Per-seed accuracy gap (pp) of each system to the cost-matched fixed-model mixture."""
    fixed = [s for s, v in summary.items() if v.get("fixed_model")]
    if len(fixed) < 2:
        return {}
    seeds = sorted({seed for s in fixed for seed in summary[s]["per_seed"]})
    gaps: dict[str, list[float]] = defaultdict(list)
    for seed in seeds:
        pts = [
            (summary[s]["per_seed"][seed][cost_key], summary[s]["per_seed"][seed]["accuracy"])
            for s in fixed
            if seed in summary[s]["per_seed"]
        ]
        front = mixture_frontier(pts)
        xs, ys = [p[0] for p in front], [p[1] for p in front]
        for s, v in summary.items():
            m = v["per_seed"].get(seed)
            if m is None or not np.isfinite(m.get(cost_key, np.nan)):
                continue
            gaps[s].append(100.0 * (m["accuracy"] - float(np.interp(m[cost_key], xs, ys))))
    return {s: mean_std(g) for s, g in gaps.items()}


def compute_summary(records: Sequence[Record], meta: ReportMeta) -> dict[str, Any]:
    n_models = len(meta.model_order)
    systems = list(dict.fromkeys(r["system"] for r in records))
    summary: dict[str, Any] = {}
    for system in systems:
        rs = [r for r in records if r["system"] == system]
        per_seed = {seed: system_metrics(v, n_models) for (seed,), v in _by(rs, "seed").items()}
        by_lang: dict[str, dict[int, dict[str, float]]] = defaultdict(dict)
        by_cat: dict[str, dict[int, dict[str, float]]] = defaultdict(dict)
        for (seed, lang), v in _by(rs, "seed", "language_variant").items():
            by_lang[lang][seed] = {
                **quality_metrics(v),
                **reliability_metrics(v),
                "escalation_rate": float(np.mean([r["escalated"] for r in v])),
                "language_id_accuracy": float(
                    np.mean([r["detected_language"] == r["language"] for r in v])
                ),
            }
        for (seed, cat), v in _by(rs, "seed", "category").items():
            by_cat[cat][seed] = {
                **quality_metrics(v),
                "task_id_accuracy": float(
                    np.mean([r["predicted_category"] == r["category"] for r in v])
                ),
            }
        summary[system] = {
            "group": meta.system_groups.get(system, "baseline"),
            "fixed_model": fixed_model_of(rs),
            "per_seed": per_seed,
            "metrics": aggregate_seeds(per_seed),
            "by_language": {k: aggregate_seeds(v) for k, v in sorted(by_lang.items())},
            "by_category": {k: aggregate_seeds(v) for k, v in sorted(by_cat.items())},
            "acceptance_by_model": {
                model: aggregate_seeds(
                    {
                        seed: acceptance_metrics(v)
                        for (seed,), v in _by(
                            [r for r in rs if r["attempts"][0]["model"] == model], "seed"
                        ).items()
                    }
                )
                for model in meta.model_order
            },
        }
    return summary


def paired_comparisons(records: Sequence[Record], reference: str) -> dict[str, dict[str, float]]:
    """Accuracy difference of every system vs the reference on identical (seed, item) pairs."""
    ref = {(r["seed"], r["item_id"]): r["correct"] for r in records if r["system"] == reference}
    out = {}
    for system in dict.fromkeys(r["system"] for r in records):
        if system == reference:
            continue
        pairs = [
            (float(r["correct"]), float(ref[(r["seed"], r["item_id"])]))
            for r in records
            if r["system"] == system and (r["seed"], r["item_id"]) in ref
        ]
        if not pairs:
            continue
        a, b = np.array(pairs).T
        res = paired_bootstrap(a, b)
        res["mcnemar_p"] = mcnemar_exact(a.astype(bool), b.astype(bool))
        out[system] = res
    return out


# ----------------------------------------------------------------------- tables
def _ms(
    agg: dict[str, dict[str, float]], key: str, percent: bool = False, digits: int = 3
) -> MeanStd:
    v = agg.get(key, {"mean": math.nan, "std": math.nan, "n": 0})
    return MeanStd(v["mean"], v["std"], int(v.get("n", 1)), digits=digits, percent=percent)


def build_tables(
    summary: dict[str, Any],
    comparisons: dict[str, dict[str, float]],
    errors: dict[str, Any],
    meta: ReportMeta,
) -> list[Table]:
    note = SIMULATED_NOTE if meta.simulated else ""
    cost_key = "cost_usd_mean" if meta.cost_unit == "usd" else "tflops_mean"
    cost_label = "Cost/query (USD)" if meta.cost_unit == "usd" else "Compute/query (TFLOPs)"
    seeds_n = max(
        (int(v["metrics"].get("accuracy", {}).get("n", 1)) for v in summary.values()), default=1
    )
    suffix = f" Mean ± std over {seeds_n} seeds." if seeds_n > 1 else ""

    main = Table(
        "main_results",
        "Quality, reliability and cost of all systems (test split)." + suffix,
        [
            "System",
            "Group",
            "Accuracy (%)",
            "Macro-acc. lang. (%)",
            cost_label,
            "Latency mean (s)",
            "Escalation rate (%)",
        ],
        note=note,
    )
    routing = Table(
        "routing",
        "Routing quality relative to the cost-optimal oracle." + suffix,
        [
            "System",
            "Routing acc. (%)",
            "Unnecessary large-model use (%)",
            "Incorrect small-model routing (%)",
            "Oracle acc. (%)",
        ],
        note=note,
    )
    eff = Table(
        "efficiency",
        "Cost and latency." + suffix,
        [
            "System",
            "Input tok./query",
            "Output tok./query",
            cost_label,
            "Latency p50 (s)",
            "Latency p95 (s)",
            "Calls/query",
        ],
        note=note,
    )
    esc = Table(
        "escalation",
        "Escalation behaviour (systems that escalate)." + suffix,
        [
            "System",
            "Escalation rate (%)",
            "Precision (%)",
            "Recall (%)",
            "Initial errors corrected (%)",
            "Initially-correct broken (%)",
            "Escalation cost share (%)",
        ],
        note=note,
    )
    calib = Table(
        "calibration",
        "Confidence quality of the initial answer (error detection)." + suffix,
        ["System", "AUROC", "AUPRC", "ECE", "Brier", "AURC", "Error rate (%)"],
        note=note,
    )
    for s, v in summary.items():
        m = v["metrics"]
        main.add(
            s,
            v["group"],
            _ms(m, "accuracy", True),
            _ms(m, "macro_accuracy_language", True),
            _ms(m, cost_key, digits=4 if meta.cost_unit == "usd" else 3),
            _ms(m, "latency_mean_s"),
            _ms(m, "escalation_rate", True),
        )
        if "routing_accuracy" in m:
            routing.add(
                s,
                _ms(m, "routing_accuracy", True),
                _ms(m, "unnecessary_large_model_rate", True),
                _ms(m, "incorrect_small_model_rate", True),
                _ms(m, "oracle_accuracy", True),
            )
        eff.add(
            s,
            _ms(m, "input_tokens_mean", digits=1),
            _ms(m, "output_tokens_mean", digits=1),
            _ms(m, cost_key, digits=4 if meta.cost_unit == "usd" else 3),
            _ms(m, "latency_p50_s"),
            _ms(m, "latency_p95_s"),
            _ms(m, "calls_mean", digits=2),
        )
        if m.get("escalation_rate", {}).get("mean", 0) > 0:
            esc.add(
                s,
                _ms(m, "escalation_rate", True),
                _ms(m, "escalation_precision", True),
                _ms(m, "escalation_recall", True),
                _ms(m, "initial_errors_corrected", True),
                _ms(m, "initial_correct_broken", True),
                _ms(m, "escalation_cost_share", True),
            )
        if "rel_auroc_error_detection" in m:
            calib.add(
                s,
                _ms(m, "rel_auroc_error_detection"),
                _ms(m, "rel_auprc_error_detection"),
                _ms(m, "rel_ece"),
                _ms(m, "rel_brier"),
                _ms(m, "rel_aurc"),
                _ms(m, "rel_error_rate", True),
            )

    languages = sorted({lang for v in summary.values() for lang in v["by_language"]})
    lang_tab = Table(
        "language_breakdown",
        "Accuracy (%) by language / variant." + suffix,
        ["System", *languages],
        note=note,
    )
    lang_esc = Table(
        "language_reliability",
        "Error-detection AUROC of initial confidence, by language." + suffix,
        ["System", *languages],
        note=note,
    )
    for s, v in summary.items():
        lang_tab.add(
            s, *[_ms(v["by_language"].get(lang, {}), "accuracy", True) for lang in languages]
        )
        lang_esc.add(
            s,
            *[
                _ms(v["by_language"].get(lang, {}), "rel_auroc_error_detection")
                for lang in languages
            ],
        )

    tables = [main, routing, eff, esc, calib, lang_tab, lang_esc]
    accept = Table(
        "acceptance",
        "Realised risk of the acceptance rule: error rate among *accepted* "
        "initial answers, by the model that produced them. Compare with the target "
        "risk of risk-controlled systems." + suffix,
        ["System", "Model", "Acceptance rate (%)", "Accepted error rate (%)", "Accepted / seed"],
        note=note,
    )
    for s, v in summary.items():
        for model, agg in v.get("acceptance_by_model", {}).items():
            if agg.get("n_accepted", {}).get("mean", 0) > 0 and v["group"] != "oracle":
                accept.add(
                    s,
                    model,
                    _ms(agg, "acceptance_rate", True),
                    _ms(agg, "accepted_error_rate", True),
                    _ms(agg, "n_accepted", digits=0),
                )
    tables.append(accept)
    gaps = mixture_gaps(summary, cost_key)
    if gaps:
        mix = Table(
            "cost_matched_mixture",
            "Accuracy relative to the best cost-matched random mixture of the fixed-model "
            "systems (upper concave hull; per seed, then mean ± std). Positive = the "
            "system adds value beyond how much compute it spends." + suffix,
            ["System", "Group", cost_label, "Accuracy (%)", "Gap vs mixture (pp)"],
            note=note,
        )
        for s, v in summary.items():
            if s in gaps:
                g = gaps[s]
                mix.add(
                    s,
                    v["group"],
                    _ms(v["metrics"], cost_key, digits=4 if meta.cost_unit == "usd" else 3),
                    _ms(v["metrics"], "accuracy", True),
                    MeanStd(g["mean"], g["std"], int(g["n"]), digits=1),
                )
        tables.append(mix)
    ablations = {s: v for s, v in summary.items() if v["group"] == "ablation"}
    if ablations and meta.reference_system:
        ref = summary[meta.reference_system]["metrics"]
        abl = Table(
            "ablations",
            f"Ablations relative to {meta.reference_system}." + suffix,
            [
                "System",
                "Accuracy (%)",
                "Δ acc. vs ref. (pp)",
                "95% CI (pp)",
                cost_label,
                "Escalation rate (%)",
            ],
            note=note,
        )
        abl.add(
            meta.reference_system,
            _ms(ref, "accuracy", True),
            "0.0",
            "–",
            _ms(ref, cost_key, digits=4 if meta.cost_unit == "usd" else 3),
            _ms(ref, "escalation_rate", True),
        )
        for s, v in ablations.items():
            c = comparisons.get(s, {})
            delta = f"{100 * c['diff']:+.1f}" if c else "–"
            ci = f"[{100 * c['ci_low']:+.1f}, {100 * c['ci_high']:+.1f}]" if c else "–"
            abl.add(
                s,
                _ms(v["metrics"], "accuracy", True),
                delta,
                ci,
                _ms(v["metrics"], cost_key, digits=4 if meta.cost_unit == "usd" else 3),
                _ms(v["metrics"], "escalation_rate", True),
            )
        tables.append(abl)
    if comparisons and meta.reference_system:
        cmp_tab = Table(
            "significance",
            f"Paired accuracy difference vs {meta.reference_system} "
            "(pooled over seeds; bootstrap CI and exact McNemar test).",
            ["System", "Δ acc. (pp)", "95% CI (pp)", "Bootstrap p", "McNemar p", "n"],
            note=note,
        )
        for s, c in comparisons.items():
            cmp_tab.add(
                s,
                f"{100 * c['diff']:+.1f}",
                f"[{100 * c['ci_low']:+.1f}, {100 * c['ci_high']:+.1f}]",
                f"{c['p_value']:.3g}",
                f"{c['mcnemar_p']:.3g}",
                int(c["n"]),
            )
        tables.append(cmp_tab)

    labels = list(TAXONOMY)
    err = Table(
        "error_analysis",
        "Failure labels per system (counts; an example can carry several labels).",
        ["System", "Wrong", *labels],
        note=note,
    )
    for s in summary:
        counts = errors["per_system"].get(s, {})
        err.add(s, errors["n_wrong"].get(s, 0), *[counts.get(lab, 0) for lab in labels])
    tables.append(err)
    return tables


# ---------------------------------------------------------------------- figures
def build_figures(
    records: Sequence[Record],
    summary: dict[str, Any],
    errors: dict[str, Any],
    meta: ReportMeta,
    out_dir: Path,
) -> list[str]:
    fw = plots.FigureWriter(out_dir, meta.figure_formats, meta.simulated)
    cost_key = "cost_usd_mean" if meta.cost_unit == "usd" else "tflops_mean"
    cost_label = (
        "mean cost per query (USD)"
        if meta.cost_unit == "usd"
        else "mean compute per query (TFLOPs, estimated)"
    )
    fixed_pts = [
        (v["metrics"][cost_key]["mean"], v["metrics"]["accuracy"]["mean"])
        for v in summary.values()
        if v.get("fixed_model") and cost_key in v["metrics"]
    ]
    plots.tradeoff(
        fw,
        summary,
        cost_key,
        cost_label,
        "accuracy",
        "accuracy",
        "pareto_accuracy_vs_cost",
        "Quality vs cost",
        frontier=mixture_frontier(fixed_pts) if len(fixed_pts) >= 2 else None,
    )
    plots.tradeoff(
        fw,
        summary,
        "latency_mean_s",
        "mean latency per query (s)",
        "accuracy",
        "accuracy",
        "pareto_accuracy_vs_latency",
        "Quality vs latency",
    )
    plots.tradeoff(
        fw,
        summary,
        "escalation_rate",
        "escalation rate",
        cost_key,
        cost_label,
        "cost_vs_escalation_rate",
        "Cost vs escalation rate",
    )

    ref = meta.reference_system or next(iter(summary), None)
    if ref is None:
        return fw.written
    ref_records = [r for r in records if r["system"] == ref]

    # Accuracy of each model alone (from the per-model outcomes on the test split).
    with_outcomes = [r for r in ref_records if "model_outcomes" in r]
    if with_outcomes:
        accs = [
            float(np.mean([r["model_outcomes"][m] for r in with_outcomes]))
            for m in meta.model_order
        ]
        plots.single_bars(
            fw,
            meta.model_order,
            accs,
            "accuracy_by_model",
            "Accuracy of each model alone (test split, all seeds)",
            "accuracy",
        )

    # Accuracy by language for up to four systems (reference first).
    fixed = [s for s in summary if summary[s]["group"] == "baseline"]
    chosen = [ref, *[s for s in fixed if s != ref]][:3]
    oracle = [s for s in summary if summary[s]["group"] == "oracle"][:1]
    chosen = list(dict.fromkeys(chosen + oracle))[:4]
    languages = sorted({lang for s in chosen for lang in summary[s]["by_language"]})
    data = {
        lang: {
            s: summary[s]["by_language"].get(lang, {}).get("accuracy", {}).get("mean", math.nan)
            for s in chosen
        }
        for lang in languages
    }
    plots.grouped_bars(fw, data, chosen, "accuracy_by_language", "Accuracy by language", "accuracy")

    # Reliability diagrams of the reference system, overall and per language.
    def conf_pairs(rs: Sequence[Record]) -> tuple[np.ndarray, np.ndarray]:
        rs = [r for r in rs if r["attempts"][0]["confidence"] is not None]
        return (
            np.array([r["attempts"][0]["confidence"] for r in rs], dtype=float),
            np.array([r["initial_correct"] for r in rs], dtype=bool),
        )

    groups = {"all languages": conf_pairs(ref_records)}
    for (lang,), rs in sorted(_by(ref_records, "language_variant").items()):
        groups[lang] = conf_pairs(rs)
    plots.reliability_diagram(
        fw, groups, "reliability_diagram", f"Reliability of initial-answer confidence ({ref})"
    )
    per_model = {
        m: conf_pairs([r for r in ref_records if r["routed_model"] == m]) for m in meta.model_order
    }
    plots.reliability_diagram(
        fw, per_model, "calibration_by_model", f"Calibration by routed model ({ref})"
    )

    n = len(meta.model_order)
    if with_outcomes:
        plots.confusion_heatmap(
            fw,
            routing_confusion(ref_records, n),
            meta.model_order,
            "router_confusion_matrix",
            f"Router confusion matrix ({ref})",
        )
    diff = defaultdict(list)
    for r in ref_records:
        diff[r["language_variant"]].append(r["difficulty_score"])
    plots.difficulty_distribution(
        fw,
        dict(sorted(diff.items())),
        "difficulty_distribution",
        f"Estimated query difficulty by language ({ref})",
    )
    shares = {}
    for s in summary:
        rs = [r for r in records if r["system"] == s]
        tiers = np.array([r["routed_tier"] for r in rs])
        shares[s] = [float((tiers == t).mean()) for t in range(n)]
    plots.model_selection(fw, shares, meta.model_order)

    counts = errors["per_system"].get(ref, {})
    labels = [lab for lab in TAXONOMY if counts.get(lab)]
    plots.single_bars(
        fw,
        labels,
        [counts[lab] for lab in labels],
        "error_types",
        f"Failure labels ({ref})",
        "number of test examples",
    )
    return fw.written


# ---------------------------------------------------------------------- report
def write_error_report(errors: dict[str, Any], meta: ReportMeta, path: Path) -> None:
    lines = ["# Error analysis", ""]
    if meta.simulated:
        lines += [f"> {SIMULATED_NOTE}", ""]
    lines += [
        "Labels are assigned automatically from observable signals and are intended to",
        "guide manual inspection. An example may carry several labels.",
        "",
        "## Taxonomy",
        "",
    ]
    lines += [f"- **{k}**: {v}" for k, v in errors["taxonomy"].items()]
    lines += ["", "## Counts per system", ""]
    labels = list(errors["taxonomy"])
    lines.append("| System | Records | Wrong | " + " | ".join(labels) + " |")
    lines.append("|---|---:|---:|" + "---:|" * len(labels))
    for s, n in errors["n_records"].items():
        c = errors["per_system"].get(s, {})
        lines.append(
            f"| {s} | {n} | {errors['n_wrong'].get(s, 0)} | "
            + " | ".join(str(c.get(lab, 0)) for lab in labels)
            + " |"
        )
    lines += ["", "## Counts per language (all systems)", ""]
    lines.append("| Language | " + " | ".join(labels) + " |")
    lines.append("|---|" + "---:|" * len(labels))
    for lang, c in sorted(errors["per_language"].items()):
        lines.append(f"| {lang} | " + " | ".join(str(c.get(lab, 0)) for lab in labels) + " |")
    lines += ["", "## Examples (first five per label)", ""]
    for lab, exs in errors["examples"].items():
        lines.append(f"### {lab}")
        for e in exs:
            lines.append(
                f"- `{e['system']}` / `{e['item_id']}` ({e['language']}): "
                f"gold={e['gold']!r}, answer={e['final_answer']!r}"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_report(
    records: list[Record],
    meta: ReportMeta,
    run_dir: str | Path,
    figures: bool = True,
    tables: bool = True,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    for sub in ("processed", "tables", "figures"):
        (run_dir / sub).mkdir(parents=True, exist_ok=True)
    summary = compute_summary(records, meta)
    comparisons = (
        paired_comparisons(records, meta.reference_system) if meta.reference_system else {}
    )
    errors = analyze_errors(records)
    metrics = {
        "simulated": meta.simulated,
        "model_order": meta.model_order,
        "reference_system": meta.reference_system,
        "systems": summary,
        "paired_vs_reference": comparisons,
        "errors": {k: v for k, v in errors.items() if k != "examples"},
    }
    (run_dir / "processed" / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8"
    )
    write_error_report(errors, meta, run_dir / "processed" / "error_analysis.md")
    if tables:
        for t in build_tables(summary, comparisons, errors, meta):
            t.save(run_dir / "tables")
    if figures:
        written = build_figures(records, summary, errors, meta, run_dir / "figures")
        logger.info("Wrote %d figures to %s", len(written), run_dir / "figures")
    return metrics


def _json_default(o: Any) -> Any:
    if isinstance(o, np.integer | np.floating):
        return o.item()
    raise TypeError(f"not JSON serialisable: {type(o)}")
