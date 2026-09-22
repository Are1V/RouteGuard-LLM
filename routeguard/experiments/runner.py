"""Benchmark runner: one command from an experiment config to a versioned run.

Protocol for every seed and every system (see docs/research_methodology.md):

1. Split items into train / calibration / test (stratified, parallel groups intact).
2. Fit the task classifier (if learned) on **train** queries.
3. Profile every pool model on **train** (correctness only) and fit the difficulty
   estimator and router.
4. Profile every pool model on **calibration** (with confidence) and fit
   calibrators and risk-controlled thresholds.
5. Profile every model on **test** for correctness only. This is used for the
   oracle and routing *analysis*, never for fitting.
6. Run the full pipeline on each test query and score it deterministically.

Fitted components record the ids they were trained on, and the runner asserts
that none of them is a test id.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from routeguard.benchmarks.loaders import dataset_fingerprint, describe, load_all
from routeguard.benchmarks.schema import Item
from routeguard.benchmarks.splits import make_splits
from routeguard.complexity import TrainingExample
from routeguard.confidence import CalibrationRecord
from routeguard.config import ExperimentConfig, PipelineConfig, SystemConfig, dump_config
from routeguard.context import CallContext
from routeguard.evaluation.records import build_record, score_item
from routeguard.evaluation.report import ReportMeta, build_report
from routeguard.evaluation.scoring import Score
from routeguard.models import GenerationCache, ModelPool, ModelSpec
from routeguard.pipeline import RouteGuardPipeline
from routeguard.router.oracle import OracleRouter
from routeguard.tracking.run import JsonlWriter, RunDirectory, environment, git_state
from routeguard.types import Query
from routeguard.utils.seeding import set_global_seed

logger = logging.getLogger(__name__)


class LeakageError(AssertionError):
    pass


class BenchmarkRunner:
    def __init__(
        self,
        config: ExperimentConfig,
        output_dir: str | None = None,
        limit: int | None = None,
        seeds: Sequence[int] | None = None,
        systems: Sequence[str] | None = None,
        figures: bool | None = None,
    ):
        self.config = config
        self.output_dir = output_dir or config.output_dir
        self.limit = limit
        self.seeds = list(seeds) if seeds else list(config.seeds)
        self.systems = [s for s in config.systems if not systems or s.name in systems]
        if systems and len(self.systems) != len(set(systems)):
            missing = set(systems) - {s.name for s in self.systems}
            raise ValueError(f"Unknown systems requested: {sorted(missing)}")
        self.figures = config.report.figures if figures is None else figures
        self._pools: dict[str, ModelPool] = {}
        self._cache: GenerationCache | None = None
        self._scores: dict[tuple[str, str | None], Score] = {}

    # ------------------------------------------------------------------ helpers
    def _pool(self, cfg: PipelineConfig) -> ModelPool:
        key = str([m.model_dump() for m in cfg.models])
        if key not in self._pools:
            if cfg.cache.enabled and self._cache is None:
                self._cache = GenerationCache(cfg.cache.path)
            specs = [ModelSpec(**m.model_dump()) for m in cfg.models]
            self._pools[key] = ModelPool(specs, cache=self._cache if cfg.cache.enabled else None)
        return self._pools[key]

    def _score(self, item: Item, answer: str | None) -> bool:
        key = (item.id, answer)
        if key not in self._scores:
            self._scores[key] = score_item(answer, item, self.config.scoring)
        return self._scores[key].correct

    def _warm(
        self, pipe: RouteGuardPipeline, items: Sequence[Item], samples: Sequence[Item] = ()
    ) -> None:
        """Batch-generate every model's initial answer for ``items`` and, for sampling-based
        confidence, the confidence samples for ``samples`` (fills the cache).

        The requests are built exactly as the pipeline builds them later (same messages, seeds
        and sampling settings), so the later per-query calls are cache hits. Generating them here
        in large batches is much faster than one small batch per query.
        """
        queries = [it.to_query() for it in items]
        analyses = [pipe.analyze(q) for q in queries]
        sampled = {it.id for it in samples}
        estimator = pipe.confidence
        n_samples = int(getattr(estimator, "n_samples", 0) or 0)
        temperature = float(getattr(estimator, "temperature", 0.0) or 0.0)
        for model in pipe.pool.names:
            llm = pipe.pool.get(model)
            requests = []
            for q, a in zip(queries, analyses, strict=True):
                ctx = CallContext(pipe.pool, q, pipe.seed)
                messages = pipe.messages_for(q, a)
                requests.append(
                    ctx._request(model, messages, "initial", 0.0, 0, None, {"strategy": "default"})
                )
                if n_samples and q.id in sampled:
                    requests.extend(
                        ctx._request(
                            model, messages, "confidence_sample", temperature, i, None, None
                        )
                        for i in range(n_samples)
                    )
            t0 = time.perf_counter()
            llm.generate_batch(requests)
            logger.info(
                "  warmed %-10s on %d queries in %.1fs",
                model,
                len(requests),
                time.perf_counter() - t0,
            )

    def _outcomes(
        self,
        pipe: RouteGuardPipeline,
        items: Sequence[Item],
        assess: bool,
    ) -> list[tuple[Item, Query, Any, dict[str, Any]]]:
        rows = []
        for it in items:
            q = it.to_query()
            analysis, attempts = pipe.profile(q, assess=assess)
            rows.append((it, q, analysis, attempts))
        return rows

    # --------------------------------------------------------------------- run
    def fit(
        self, pipe: RouteGuardPipeline, train: list[Item], calib: list[Item], test: list[Item]
    ) -> dict[str, dict[str, bool]]:
        """Fit all supervised components; return per-model test outcomes (analysis only)."""
        pipe.fit_task_classifier([it.to_query() for it in train])
        # Generate every model's initial answers for all splits in large batches up front
        # (cached; later profiling and evaluation calls are cache hits).
        self._warm(pipe, [*train, *calib, *test], samples=[*calib, *test])

        if pipe.needs_training_data:
            examples = []
            for it, q, analysis, attempts in self._outcomes(pipe, train, assess=False):
                examples.append(
                    TrainingExample(
                        q,
                        analysis,
                        {m: self._score(it, a.answer) for m, a in attempts.items()},
                        latency={
                            m: float(a.info.get("latency_s", 0.0)) for m, a in attempts.items()
                        },
                    )
                )
            pipe.fit_difficulty_and_router(examples)

        if pipe.needs_calibration_data:
            risk = pipe.config.escalation.triggers.risk_control
            conditional = risk is not None and risk.conditional_on_routing
            records = []
            for it, q, analysis, attempts in self._outcomes(pipe, calib, assess=True):
                routed_to = pipe.route(q, analysis) if conditional else None
                for m, a in attempts.items():
                    if a.confidence is not None:
                        records.append(
                            CalibrationRecord(
                                m,
                                analysis.language,
                                a.confidence.raw,
                                self._score(it, a.answer),
                                routed=routed_to is None or routed_to == m,
                            )
                        )
            pipe.fit_calibration(records)

        test_outcomes = {
            it.id: {m: self._score(it, a.answer) for m, a in attempts.items()}
            for it, _q, _a, attempts in self._outcomes(pipe, test, assess=False)
        }
        if isinstance(pipe.router, OracleRouter):
            pipe.router.set_outcomes(test_outcomes)
        self._check_leakage(pipe, {it.id for it in test})
        return test_outcomes

    @staticmethod
    def _check_leakage(pipe: RouteGuardPipeline, test_ids: set[str]) -> None:
        for component in (pipe.difficulty, pipe.router):
            trained: set[str] = getattr(component, "trained_ids", set())
            overlap = trained & test_ids
            if overlap:
                raise LeakageError(f"{component.name} was trained on {len(overlap)} test items")

    def run_system(
        self,
        system: SystemConfig,
        seed: int,
        splits: Any,
        writer: JsonlWriter,
    ) -> tuple[float, dict[str, Any]]:
        cfg = self.config.system_pipeline(system)
        cfg.seed = seed
        pool = self._pool(cfg)
        pipe = RouteGuardPipeline(cfg, pool=pool)
        t0 = time.perf_counter()
        test_outcomes = self.fit(pipe, splits.train, splits.calibration, splits.test)
        doc_text = None
        if pipe.retriever is not None:
            docs = {d.id: d.text for d in pipe.retriever.documents}
            doc_text = docs.__getitem__
        for i, item in enumerate(splits.test, 1):
            result = pipe.run(item.to_query())
            record = build_record(
                result,
                item,
                self.config.scoring,
                seed,
                pool.names,
                test_outcomes.get(item.id),
                self._scores,
                doc_text,
            )
            record["simulated"] = pool.simulated
            writer.write(record)
            if i % 100 == 0:
                logger.info("  %s seed %d: %d/%d", system.name, seed, i, len(splits.test))
        fitted = {m: vars(t) for m, t in pipe.policy.thresholds.items()}
        initial = {m: vars(t) for m, t in pipe.policy.initial_thresholds.items()}
        return time.perf_counter() - t0, {
            "thresholds": fitted,
            "initial_thresholds": initial,
            "calibration_fallbacks": getattr(pipe.calibration, "fallbacks", []),
        }

    def run(self) -> Path:
        cfg = self.config
        items = load_all(cfg.data)
        if self.limit:
            items = items[: self.limit]
        info = describe(items)
        logger.info("Loaded %d items: %s", len(items), info["by_language"])
        run = RunDirectory(self.output_dir, cfg.name)
        run.write_text("config.yaml", dump_config(cfg))
        base_models = cfg.system_pipeline(self.systems[0]).models
        simulated = any(
            m.backend == "simulated" for s in self.systems for m in cfg.system_pipeline(s).models
        )
        manifest: dict[str, Any] = {
            "name": cfg.name,
            "description": cfg.description,
            "started": time.strftime("%FT%T%z"),
            "git": git_state(),
            "environment": environment(),
            "seeds": self.seeds,
            "systems": {s.name: s.group for s in self.systems},
            "data": info,
            "data_fingerprint": dataset_fingerprint(items),
            "simulated": simulated,
            "models": [m.model_dump() for m in base_models],
            "timings_s": {},
            "fitted": {},
        }
        run.write_json("manifest.json", manifest)
        if simulated:
            logger.warning("SIMULATED backend in use: results are NOT real model results")

        raw_files: list[Path] = []
        manifest["status"] = "running"
        try:
            for seed in self.seeds:
                set_global_seed(seed)
                splits = make_splits(items, cfg.splits, seed)
                manifest["fitted"][f"seed{seed}_split_sizes"] = {
                    "train": len(splits.train),
                    "calibration": len(splits.calibration),
                    "test": len(splits.test),
                }
                for system in self.systems:
                    path = run.path / "raw" / f"{system.name}_seed{seed}.jsonl"
                    logger.info("[seed %d] %s", seed, system.name)
                    with JsonlWriter(path) as writer:
                        elapsed, fitted = self.run_system(system, seed, splits, writer)
                    manifest["timings_s"][f"{system.name}/seed{seed}"] = round(elapsed, 2)
                    manifest["fitted"][f"{system.name}/seed{seed}"] = fitted
                    raw_files.append(path)

        except BaseException as exc:
            # A failed run is recorded as failed, never left looking like a partial success.
            manifest["status"] = "failed"
            manifest["error"] = f"{type(exc).__name__}: {exc}"
            run.write_json("manifest.json", manifest)
            raise
        manifest["status"] = "completed"
        manifest["finished"] = time.strftime("%FT%T%z")
        manifest["resources"] = {name: pool.resource_stats() for name, pool in self._pools.items()}
        if self._cache is not None:
            manifest["cache"] = {
                "path": str(self._cache.path),
                "hits": self._cache.hits,
                "misses": self._cache.misses,
            }
        run.write_json("manifest.json", manifest)
        run.write_json("processed/report_meta.json", self.report_meta(simulated).__dict__)

        from routeguard.evaluation.report import load_records

        build_report(
            load_records(raw_files),
            self.report_meta(simulated),
            run.path,
            figures=self.figures,
            tables=cfg.report.tables,
        )
        logger.info("Run written to %s", run.path)
        return run.path

    def report_meta(self, simulated: bool) -> ReportMeta:
        cfg = self.config
        models = cfg.system_pipeline(self.systems[0]).models
        priced = any(m.price_input_per_1k or m.price_output_per_1k for m in models)
        reference = cfg.report.reference_system
        if reference and reference not in {s.name for s in self.systems}:
            reference = None
        return ReportMeta(
            model_order=[m.name for m in models],
            system_groups={s.name: s.group for s in self.systems},
            simulated=simulated,
            reference_system=reference,
            figure_formats=list(cfg.report.formats),
            cost_unit="usd" if priced else "tflops",
        )
