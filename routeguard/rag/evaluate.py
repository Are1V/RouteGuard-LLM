"""``routeguard rag-eval``: retrieval-vs-generation failure analysis across languages."""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from routeguard.answers import extract_answer
from routeguard.benchmarks.loaders import describe, load_all
from routeguard.config import DatasetConfig, PipelineConfig, ScoringConfig, load_yaml
from routeguard.evaluation import plots
from routeguard.evaluation.tables import SIMULATED_NOTE, Table
from routeguard.pipeline import RouteGuardPipeline, build_pool
from routeguard.rag.reliability import build_passage_corpus, evaluate_item, summarize
from routeguard.rag.retriever import BM25Retriever
from routeguard.tracking.run import JsonlWriter, RunDirectory, environment, git_state

logger = logging.getLogger(__name__)


class RagEvalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    pipeline: dict[str, Any]
    model: str = Field(description="pool model that answers with retrieved evidence")
    data: list[DatasetConfig]
    k: int = 3
    same_language: bool = True
    prefix_len: int | None = None
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    output_dir: str = "results/runs"


def run_rag_eval(config_path: str | Path, limit: int | None = None) -> Path:
    cfg = RagEvalConfig.model_validate(load_yaml(config_path))
    pcfg = PipelineConfig.model_validate(cfg.pipeline)
    pool = build_pool(pcfg)
    pool.spec(cfg.model)
    pipe = RouteGuardPipeline(pcfg, pool=pool)
    items = load_all(cfg.data)
    if limit:
        items = items[:limit]
    docs, rag_items = build_passage_corpus(items)
    retriever = BM25Retriever(docs, prefix_len=cfg.prefix_len)
    run = RunDirectory(cfg.output_dir, cfg.name)
    run.write_json(
        "manifest.json",
        {
            "config": cfg.model_dump(),
            "data": describe(items),
            "n_documents": len(docs),
            "git": git_state(),
            "environment": environment(),
            "simulated": pool.simulated,
        },
    )
    outcomes = []
    with JsonlWriter(run.path / "raw" / "rag_outcomes.jsonl") as writer:
        for it in rag_items:
            q = it.to_query()
            q.reference = {**(q.reference or {}), "context": it.metadata.get("gold_passage")}
            analysis = pipe.analyze(q)
            hits = retriever.search(
                q.text, k=cfg.k, language=it.language if cfg.same_language else None
            )
            evidence = [h.doc.text for h in hits]
            ctx = pipe.context(q)
            out = ctx.generate(
                cfg.model,
                pipe.messages_for(q, analysis, evidence=evidence),
                purpose="rag",
                metadata={"evidence": evidence},
            )
            answer = extract_answer(out.text, q.answer_type, q.choices)
            o = evaluate_item(it, hits, out.text, answer, cfg.scoring)
            outcomes.append(o)
            writer.write({**asdict(o), "retrieved": [h.doc.id for h in hits], "answer": answer})
    summary = summarize(outcomes)
    run.write_json("processed/rag_summary.json", summary)
    note = SIMULATED_NOTE if pool.simulated else ""
    cols = [
        "retrieval_recall_at_k",
        "mrr",
        "accuracy",
        "accuracy_given_hit",
        "accuracy_given_miss",
        "answer_without_evidence_rate",
        "groundedness_mean",
        "retrieval_failure_share",
        "generation_failure_share",
    ]
    table = Table(
        "rag_reliability",
        f"RAG reliability by language (BM25, k={cfg.k}, model={cfg.model}).",
        ["Language", "n", *cols],
        note=note,
    )
    for lang, m in [*summary["by_language"].items(), ("all", summary["overall"])]:
        table.add(lang, int(m["n"]), *[m[c] for c in cols])
    table.save(run.path / "tables")
    fw = plots.FigureWriter(run.path / "figures", simulated=pool.simulated)
    langs = list(summary["by_language"])
    data = {
        lang: {
            "retrieval recall@k": summary["by_language"][lang]["retrieval_recall_at_k"],
            "accuracy | hit": summary["by_language"][lang]["accuracy_given_hit"],
            "accuracy | miss": summary["by_language"][lang]["accuracy_given_miss"],
        }
        for lang in langs
    }
    plots.grouped_bars(
        fw,
        data,
        ["retrieval recall@k", "accuracy | hit", "accuracy | miss"],
        "rag_reliability_by_language",
        "Retrieval vs generation by language",
        "rate",
    )
    logger.info("RAG evaluation written to %s", run.path)
    print(table.to_markdown())
    return run.path
