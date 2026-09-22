"""Interactive dashboard (``routeguard demo``) — visualises one query's decision trace.

It deliberately does not look like a chatbot: every stage of the pipeline is
shown (analysis, difficulty, routing, each attempt with confidence and
verification, the escalation path, and the cost of every call).
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from routeguard.benchmarks.loaders import load_jsonl
from routeguard.config import DatasetConfig, load_pipeline_config
from routeguard.pipeline import RouteGuardPipeline
from routeguard.types import AnswerType, Attempt, PipelineResult, Query
from routeguard.utils.imports import require

CSS = """
.rg-flow {display:flex; flex-direction:column; gap:10px; font-size:14px}
.rg-row {display:flex; flex-wrap:wrap; gap:10px}
.rg-card {border:1px solid var(--border-color-primary); border-radius:10px; padding:10px 12px;
          background:var(--background-fill-secondary); flex:1 1 180px; min-width:0}
.rg-card h4 {margin:0 0 6px 0; font-size:12px; text-transform:uppercase; letter-spacing:.04em;
             color:var(--body-text-color-subdued)}
.rg-big {font-size:18px; font-weight:600; overflow-wrap:anywhere}
.rg-muted {color:var(--body-text-color-subdued); font-size:12px}
.rg-arrow {text-align:center; color:var(--body-text-color-subdued); font-size:14px}
.rg-bar {height:8px; border-radius:4px; background:var(--border-color-primary); overflow:hidden}
.rg-bar > div {height:100%; background:#2a78d6}
.rg-badge {display:inline-block; padding:1px 8px; border-radius:999px; font-size:12px;
           border:1px solid var(--border-color-primary)}
.rg-ok::before {content:"✓ "} .rg-bad::before {content:"✗ "} .rg-na::before {content:"– "}
.rg-final {border-width:2px}
.rg-warn {border:1px solid #e34948; border-radius:10px; padding:8px 12px; font-size:13px}
"""


def _esc(x: Any) -> str:
    return html.escape(str(x))


def _answer(x: str | None) -> str:
    """An unparsable generation has no answer; say so instead of rendering ``None``."""
    return _esc(x) if x else '<span class="rg-muted">no answer extracted</span>'


def _badge(passed: bool | None, text: str) -> str:
    cls = "rg-na" if passed is None else ("rg-ok" if passed else "rg-bad")
    return f'<span class="rg-badge {cls}">{_esc(text)}</span>'


def _attempt_card(i: int, a: Attempt, is_final: bool) -> str:
    conf = a.confidence
    if conf is None:
        conf_html = '<div class="rg-muted">confidence: not estimated</div>'
    else:
        kind = "calibrated P(correct)" if conf.calibrated is not None else f"raw {conf.method}"
        conf_html = (
            f'<div class="rg-muted">confidence ({_esc(kind)}): {conf.value:.3f}</div>'
            f'<div class="rg-bar"><div style="width:{100 * max(0, min(1, conf.value)):.0f}%">'
            "</div></div>"
        )
    ver = a.verification
    ver_html = (
        _badge(None, "no applicable verifier")
        if ver is None or ver.passed is None
        else _badge(
            ver.passed, f"{ver.verifier}: {'passed' if ver.passed else ver.reason or 'failed'}"
        )
    )
    rel = _badge(
        bool(a.reliable), "reliable" if a.reliable else "unreliable: " + ", ".join(a.trigger)
    )
    tools = a.info.get("tool_calls")
    tool_html = f'<div class="rg-muted">tool calls: {_esc(tools)}</div>' if tools else ""
    return (
        f'<div class="rg-card {"rg-final" if is_final else ""}"><h4>Attempt {i} · '
        f"{_esc(a.stage)} · {_esc(a.model)}{' · FINAL' if is_final else ''}</h4>"
        f'<div class="rg-big">{_answer(a.answer)}</div>{conf_html}'
        f'<div style="margin-top:6px">{ver_html} {rel}</div>{tool_html}</div>'
    )


def render_trace(result: PipelineResult, simulated: bool) -> str:
    a, d, r = result.analysis, result.difficulty, result.routing
    t = result.totals()
    warn = (
        (
            '<div class="rg-warn">Simulated backend: this trace illustrates the pipeline; '
            "it is not the behaviour of a real language model.</div>"
        )
        if simulated
        else ""
    )
    top = (
        f'<div class="rg-row">'
        f'<div class="rg-card"><h4>Language</h4><div class="rg-big">{_esc(a.language)}</div>'
        f'<div class="rg-muted">confidence {a.language_confidence:.2f} · scripts '
        f"{_esc(', '.join(f'{k} {v:.0%}' for k, v in a.scripts.items()))}</div></div>"
        f'<div class="rg-card"><h4>Task category</h4><div class="rg-big">{_esc(a.category)}</div>'
        f'<div class="rg-muted">confidence {a.category_confidence:.2f}</div></div>'
        f'<div class="rg-card"><h4>Difficulty</h4><div class="rg-big">{d.score:.2f} · '
        f"{_esc(d.label.value)}</div>"
        f'<div class="rg-muted">estimator: {_esc(d.estimator)}</div></div>'
        f'<div class="rg-card"><h4>Routed to</h4><div class="rg-big">{_esc(r.model)}</div>'
        f'<div class="rg-muted">{_esc(r.router)}: {_esc(r.reason)}</div></div></div>'
    )
    attempts = "".join(
        ('<div class="rg-arrow">↓ escalation</div>' if i else "")
        + _attempt_card(i, att, i == result.final_index)
        for i, att in enumerate(result.attempts)
    )
    path = " → ".join(f"{att.stage}:{att.model}" for att in result.attempts)
    by_model: dict[str, int] = {}
    for c in result.calls:
        by_model[c.model] = by_model.get(c.model, 0) + 1
    # Local backends have no price, so a $0.00000 headline would look like a bug: lead with
    # compute, which is always measured, and show the price only when one is configured.
    cost_line = (
        f"estimated cost ${t['cost_usd']:.5f}" if t["cost_usd"] > 0 else "no price configured"
    )
    cost = (
        f'<div class="rg-row">'
        f'<div class="rg-card"><h4>Final answer</h4><div class="rg-big">'
        f'{_answer(result.final_answer)}</div><div class="rg-muted">'
        f"from {_esc(result.final_model)} · "
        f"escalated: {result.escalated}</div></div>"
        f'<div class="rg-card"><h4>Latency</h4>'
        f'<div class="rg-big">{t["latency_s"]:.2f} s</div></div>'
        f'<div class="rg-card"><h4>Tokens</h4><div class="rg-big">{int(t["input_tokens"])} in · '
        f"{int(t['output_tokens'])} out</div></div>"
        f'<div class="rg-card"><h4>Compute</h4>'
        f'<div class="rg-big">{t["tflops"]:.3f} TFLOPs</div>'
        f'<div class="rg-muted">{cost_line}</div></div>'
        f'<div class="rg-card"><h4>Calls</h4><div class="rg-big">{int(t["n_calls"])}</div>'
        f'<div class="rg-muted">{_esc(by_model)}</div></div></div>'
        f'<div class="rg-muted">Escalation path: {_esc(path)}</div>'
    )
    return f'<div class="rg-flow">{warn}{top}<div class="rg-arrow">↓</div>{attempts}{cost}</div>'


def build_app(
    config_path: str | Path, examples_path: str = "benchmarks/samples/smoke.jsonl"
) -> Any:
    gr = require("gradio", "dashboard", "The dashboard")
    config = load_pipeline_config(config_path)
    pipe = RouteGuardPipeline(config)
    if pipe.needs_training_data:
        raise ValueError(
            "The dashboard needs a pipeline without learned components "
            "(or fit it with `routeguard benchmark` first)."
        )
    examples = {}
    if Path(examples_path).exists():
        for it in load_jsonl(DatasetConfig(loader="jsonl", path=examples_path, limit=3)):
            examples[f"[{it.language}] {it.question[:70]}"] = it

    def run(
        example: str | None,
        text: str,
        answer_type: str,
        options: str,
        passage: str,
    ) -> tuple[str, dict[str, Any]]:
        item = examples.get(example or "")
        if item is not None and text.strip() == item.question.strip():
            query = item.to_query()
        else:
            if not text.strip():
                return "<p>Enter a query or pick an example.</p>", {}
            choices = [c.strip() for c in options.splitlines() if c.strip()] or None
            query = Query(
                text=text,
                id="dashboard",
                answer_type=AnswerType(answer_type),
                choices=choices,
                context=passage or None,
            )
        result = pipe.run(query)
        return render_trace(result, pipe.pool.simulated), json.loads(
            json.dumps(result.to_dict(), default=str)
        )

    def pick(example: str | None) -> tuple[str, str, str, str]:
        item = examples.get(example or "")
        if item is None:
            return "", "text", "", ""
        return (
            item.question,
            item.answer_type.value,
            "\n".join(item.choices or []),
            item.context or "",
        )

    with gr.Blocks(title="RouteGuard-LLM") as app:
        gr.HTML(f"<style>{CSS}</style>")
        gr.Markdown(
            f"## RouteGuard-LLM · decision trace\nPipeline: `{config.name}` · models: "
            + " → ".join(f"`{m.name}`" for m in config.models)
            + " (weakest → strongest)"
        )
        with gr.Row():
            with gr.Column(scale=2):
                example = gr.Dropdown(list(examples), label="Example queries", value=None)
                text = gr.Textbox(label="Query", lines=3)
                with gr.Row():
                    answer_type = gr.Dropdown(
                        ["text", "numeric", "choice", "code"],
                        value="text",
                        label="Expected answer type",
                    )
                options = gr.Textbox(label="Options (one per line, for choice questions)", lines=2)
                passage = gr.Textbox(label="Passage (optional)", lines=2)
                go = gr.Button("Run pipeline", variant="primary")
            with gr.Column(scale=3):
                trace = gr.HTML()
                with gr.Accordion("Full JSON trace", open=False):
                    raw = gr.JSON()
        example.change(pick, example, [text, answer_type, options, passage])
        go.click(run, [example, text, answer_type, options, passage], [trace, raw])
    return app


def launch(
    config_path: str | Path = "configs/demo.yaml",
    port: int | None = None,
    share: bool = False,
) -> None:
    """Serve the dashboard.

    With no ``port`` Gradio picks one itself, honouring ``GRADIO_SERVER_PORT`` and
    falling forward if the first is taken. An explicit port is used as given, so a
    busy one is reported rather than silently moved.
    """
    app = build_app(config_path)
    try:
        app.launch(server_port=port, share=share)
    except OSError as exc:
        raise SystemExit(
            f"Cannot start the dashboard: {exc}\n"
            "Pass a free port with --port, or set GRADIO_SERVER_PORT."
        ) from exc
