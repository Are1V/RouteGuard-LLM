"""Command-line interface: ``routeguard <command> ...``.

Commands
--------
run            run the pipeline on queries and print the decision trace
benchmark      run an experiment config end to end (versioned run directory)
evaluate       recompute metrics / tables / error analysis from raw records
plot           regenerate figures for a run
prepare-data   download public datasets into local JSONL snapshots
generate       generate one shard of an experiment's model requests (cluster jobs)
cache-merge    merge per-shard generation caches
rag-eval       RAG reliability: retrieval vs generation failures by language
tool-eval      tool-use failure analysis
validate       validate a pipeline or experiment config without running it
components     list available backends, routers, estimators, verifiers, stages, loaders
demo           launch the interactive dashboard (needs the ``dashboard`` extra)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from routeguard import __version__
from routeguard.utils.imports import MissingDependencyError

logger = logging.getLogger("routeguard")


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "urllib3", "matplotlib", "datasets", "huggingface_hub", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ------------------------------------------------------------------------- run
def format_trace(result: Any) -> str:
    """Human-readable decision trace of one :class:`PipelineResult`."""
    a = result.analysis
    lines = [
        f"Query     : {result.query[:160]}",
        f"Analysis  : language={a.language} ({a.language_confidence:.2f})  "
        f"category={a.category} ({a.category_confidence:.2f})",
        f"Difficulty: {result.difficulty.score:.3f} [{result.difficulty.label.value}] "
        f"via {result.difficulty.estimator}",
        f"Routing   : {result.routing.model}  ({result.routing.router}: {result.routing.reason})",
    ]
    for i, att in enumerate(result.attempts):
        conf = att.confidence
        conf_s = (
            "n/a"
            if conf is None
            else (f"{conf.value:.3f}" + (" calibrated" if conf.calibrated is not None else " raw"))
        )
        ver = att.verification
        ver_s = (
            "n/a"
            if ver is None or ver.passed is None
            else ("pass" if ver.passed else f"FAIL ({ver.verifier}: {ver.reason})")
        )
        lines.append(
            f"Attempt {i} : [{att.stage}] model={att.model} answer={att.answer!r} "
            f"confidence={conf_s} verification={ver_s} "
            f"-> {'reliable' if att.reliable else 'unreliable: ' + ','.join(att.trigger)}"
        )
    t = result.totals()
    lines.append(
        f"Final     : {result.final_answer!r} from {result.final_model} "
        f"(escalated={result.escalated})"
    )
    lines.append(
        f"Cost      : {int(t['input_tokens'])} in / {int(t['output_tokens'])} out tokens, "
        f"{t['latency_s']:.2f}s, {t['tflops']:.3f} TFLOPs, ${t['cost_usd']:.5f}, "
        f"{int(t['n_calls'])} calls"
    )
    return "\n".join(lines)


def cmd_run(args: argparse.Namespace) -> int:
    from routeguard.benchmarks.loaders import load_jsonl
    from routeguard.config import DatasetConfig, load_pipeline_config
    from routeguard.pipeline import RouteGuardPipeline
    from routeguard.tracking.run import JsonlWriter
    from routeguard.types import AnswerType, Query

    config = load_pipeline_config(args.config)
    pipe = RouteGuardPipeline(config)
    if pipe.needs_training_data:
        logger.error(
            "This pipeline has learned components (difficulty/router/task classifier) "
            "that must be fitted on data; use `routeguard benchmark` instead."
        )
        return 2
    if args.query:
        queries = [Query(text=args.query, id="cli-0", answer_type=AnswerType(args.answer_type))]
    else:
        path = args.input or "benchmarks/samples/smoke.jsonl"
        items = load_jsonl(DatasetConfig(loader="jsonl", path=path, limit=args.limit))
        queries = [it.to_query() for it in items]
        if not args.input:
            print(f"(no --query/--input given: running {len(queries)} items from {path})\n")
    writer = JsonlWriter(args.output) if args.output else None
    for q in queries:
        result = pipe.run(q)
        print(format_trace(result))
        print("-" * 100)
        if writer:
            writer.write(result.to_dict())
    if writer:
        writer.close()
        print(f"Wrote {len(queries)} traces to {args.output}")
    if pipe.pool.simulated:
        print("NOTE: simulated backend - traces illustrate the pipeline, not real model behaviour.")
    return 0


# ------------------------------------------------------------------- benchmark
def cmd_benchmark(args: argparse.Namespace) -> int:
    from routeguard.config import load_experiment_config
    from routeguard.experiments.runner import BenchmarkRunner

    config = load_experiment_config(args.config)
    runner = BenchmarkRunner(
        config,
        output_dir=args.output_dir,
        limit=args.limit,
        seeds=args.seeds,
        systems=args.systems,
        figures=False if args.no_figures else None,
    )
    run_dir = runner.run()
    table = run_dir / "tables" / "main_results.md"
    if table.exists():
        print(table.read_text(encoding="utf-8"))
    print(f"Results: {run_dir}")
    return 0


# -------------------------------------------------------------------- evaluate
def _resolve_run(path: Path) -> tuple[Path, list[Path]]:
    if path.is_file() and path.suffix == ".jsonl":
        return path.parent.parent if path.parent.name == "raw" else path.parent, [path]
    if path.is_file() and path.name == "metrics.json":
        path = path.parent.parent
    raw = sorted((path / "raw").glob("*.jsonl"))
    if not raw:
        raise FileNotFoundError(f"No raw/*.jsonl records found under {path}")
    return path, raw


def _meta_for(run_dir: Path, records: list[dict[str, Any]]) -> Any:
    from routeguard.evaluation.report import ReportMeta

    meta_path = run_dir / "processed" / "report_meta.json"
    if meta_path.exists():
        return ReportMeta(**json.loads(meta_path.read_text(encoding="utf-8")))
    return ReportMeta(
        model_order=records[0]["model_order"],
        system_groups={r["system"]: "baseline" for r in records},
        simulated=any(r.get("simulated") for r in records),
    )


def cmd_evaluate(args: argparse.Namespace) -> int:
    from routeguard.evaluation.report import build_report, load_records

    run_dir, raw = _resolve_run(Path(args.path))
    records = load_records(raw)
    meta = _meta_for(run_dir, records)
    if args.reference:
        meta.reference_system = args.reference
    out = Path(args.out) if args.out else run_dir
    metrics = build_report(records, meta, out, figures=args.figures, tables=True)
    print(f"Evaluated {len(records)} records from {len(raw)} file(s) -> {out}")
    for name, s in metrics["systems"].items():
        acc = s["metrics"]["accuracy"]
        print(f"  {name:28s} accuracy {acc['mean']:.3f} ± {acc['std']:.3f}")
    return 0


def cmd_plot(args: argparse.Namespace) -> int:
    from routeguard.evaluation.errors import analyze_errors
    from routeguard.evaluation.report import build_figures, compute_summary, load_records

    run_dir, raw = _resolve_run(Path(args.path))
    records = load_records(raw)
    meta = _meta_for(run_dir, records)
    if args.formats:
        meta.figure_formats = args.formats
    out = Path(args.out) if args.out else run_dir / "figures"
    written = build_figures(
        records, compute_summary(records, meta), analyze_errors(records), meta, out
    )
    print(f"Wrote {len(written)} figures to {out}: {', '.join(written)}")
    return 0


# ---------------------------------------------------------------- prepare-data
def cmd_prepare_data(args: argparse.Namespace) -> int:
    from routeguard.benchmarks.loaders import describe, load_dataset, write_jsonl
    from routeguard.config import load_experiment_config

    config = load_experiment_config(args.config)
    out = Path(args.out)
    for ds in config.data:
        if ds.loader == "jsonl":
            continue
        items = load_dataset(ds)
        name = ds.name or ds.loader
        write_jsonl(items, out / f"{name}.jsonl")
        print(f"{name}: {describe(items)}")
    print(f"Snapshots written to {out}. Licenses: see docs/benchmarks.md")
    return 0


# -------------------------------------------------------------------- validate
def cmd_validate(args: argparse.Namespace) -> int:
    from routeguard.config import (
        ExperimentConfig,
        PipelineConfig,
        is_experiment_config,
        load_yaml,
    )

    data = load_yaml(args.config)
    if is_experiment_config(data):
        cfg = ExperimentConfig.model_validate(data)
        print(
            f"OK: experiment '{cfg.name}' with {len(cfg.systems)} systems, "
            f"{len(cfg.data)} dataset(s), seeds {cfg.seeds}"
        )
    else:
        pcfg = PipelineConfig.model_validate(data)
        print(f"OK: pipeline '{pcfg.name}' with models {[m.name for m in pcfg.models]}")
    return 0


def cmd_components(args: argparse.Namespace) -> int:
    from routeguard.benchmarks.loaders import LOADERS
    from routeguard.complexity import ESTIMATORS as DIFF
    from routeguard.confidence import ESTIMATORS as CONF
    from routeguard.escalation import STAGES
    from routeguard.models import available_backends
    from routeguard.router import ROUTERS
    from routeguard.verification import VERIFIERS

    listing = {
        "backends": available_backends(),
        "routers": sorted(ROUTERS),
        "difficulty_estimators": sorted(DIFF),
        "confidence_methods": sorted(CONF),
        "verifiers": sorted(VERIFIERS),
        "escalation_stages": sorted(STAGES),
        "dataset_loaders": sorted(LOADERS),
    }
    for k, v in listing.items():
        print(f"{k:22s} {', '.join(v)}")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    from routeguard.config import load_experiment_config
    from routeguard.experiments.sharding import ShardSpec, generate_shard

    shard = ShardSpec.parse(args.shard)
    done = generate_shard(load_experiment_config(args.config), shard, args.cache, args.models)
    print(f"shard {shard.index}/{shard.count}: generated {done} into {args.cache}")
    return 0


def cmd_cache_merge(args: argparse.Namespace) -> int:
    from routeguard.experiments.sharding import merge_caches

    total = merge_caches(args.inputs, args.out)
    print(f"merged {len(args.inputs)} cache(s) into {args.out}: {total} generations")
    return 0


def cmd_rag_eval(args: argparse.Namespace) -> int:
    from routeguard.rag.evaluate import run_rag_eval

    print(f"Results: {run_rag_eval(args.config, limit=args.limit)}")
    return 0


def cmd_tool_eval(args: argparse.Namespace) -> int:
    from routeguard.tools.run import run_tool_eval

    print(f"Results: {run_tool_eval(args.config)}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    from routeguard.dashboard import launch

    launch(args.config, port=args.port, share=args.share)
    return 0


# ------------------------------------------------------------------------ main
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="routeguard",
        description="Reliability-aware adaptive LLM "
        "routing: inference, benchmarking, and evaluation.",
    )
    p.add_argument("--version", action="version", version=f"routeguard {__version__}")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="run the pipeline on queries and print decision traces")
    r.add_argument("--config", default="configs/demo.yaml")
    r.add_argument("--query", help="a single query")
    r.add_argument("--answer-type", default="text", choices=["text", "numeric", "choice", "code"])
    r.add_argument("--input", help="JSONL file of benchmark items")
    r.add_argument("--limit", type=int, default=8, help="items per language from --input")
    r.add_argument("--output", help="write full traces to this JSONL file")
    r.set_defaults(func=cmd_run)

    b = sub.add_parser("benchmark", help="run an experiment config end to end")
    b.add_argument("--config", required=True)
    b.add_argument("--output-dir")
    b.add_argument("--limit", type=int, help="use only the first N items (debugging)")
    b.add_argument("--seeds", type=int, nargs="+")
    b.add_argument("--systems", nargs="+", help="run only these systems")
    b.add_argument("--no-figures", action="store_true")
    b.set_defaults(func=cmd_benchmark)

    e = sub.add_parser("evaluate", help="recompute metrics/tables from raw records")
    e.add_argument("path", help="run directory, raw/*.jsonl file, or processed/metrics.json")
    e.add_argument("--out", help="output directory (default: the run directory)")
    e.add_argument("--reference", help="reference system for paired comparisons")
    e.add_argument("--figures", action="store_true", help="also regenerate figures")
    e.set_defaults(func=cmd_evaluate)

    pl = sub.add_parser("plot", help="regenerate figures for a run")
    pl.add_argument("path", help="run directory or processed/metrics.json")
    pl.add_argument("--out")
    pl.add_argument("--formats", nargs="+", choices=["png", "pdf", "svg"])
    pl.set_defaults(func=cmd_plot)

    d = sub.add_parser("prepare-data", help="download datasets of an experiment to JSONL")
    d.add_argument("--config", required=True)
    d.add_argument("--out", default="data")
    d.set_defaults(func=cmd_prepare_data)

    v = sub.add_parser("validate", help="validate a pipeline or experiment config")
    v.add_argument("config")
    v.set_defaults(func=cmd_validate)

    g = sub.add_parser("generate", help="generate one shard of an experiment's requests (clusters)")
    g.add_argument("--config", required=True)
    g.add_argument("--shard", default="0/1", help="i/N (0-based) or 'auto' in a SLURM array job")
    g.add_argument("--cache", required=True, help="per-shard SQLite cache to write")
    g.add_argument("--models", nargs="+", help="only these pool models (default: all)")
    g.set_defaults(func=cmd_generate)

    cm = sub.add_parser("cache-merge", help="merge per-shard generation caches")
    cm.add_argument("inputs", nargs="+")
    cm.add_argument("--out", required=True)
    cm.set_defaults(func=cmd_cache_merge)

    rg = sub.add_parser("rag-eval", help="retrieval vs generation failure analysis")
    rg.add_argument("--config", required=True)
    rg.add_argument("--limit", type=int)
    rg.set_defaults(func=cmd_rag_eval)

    te = sub.add_parser("tool-eval", help="tool-use failure analysis")
    te.add_argument("--config", required=True)
    te.set_defaults(func=cmd_tool_eval)

    c = sub.add_parser("components", help="list available components")
    c.set_defaults(func=cmd_components)

    dm = sub.add_parser("demo", help="launch the interactive dashboard")
    dm.add_argument("--config", default="configs/demo.yaml")
    dm.add_argument("--port", type=int, help="default: Gradio picks a free port")
    dm.add_argument("--share", action="store_true")
    dm.set_defaults(func=cmd_demo)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _setup_logging(args.verbose)
    try:
        return int(args.func(args))
    except (FileNotFoundError, ValueError, MissingDependencyError) as exc:
        logger.error("%s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
