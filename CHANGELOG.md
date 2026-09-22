# Changelog

## Unreleased

Web application and API fixes. No routing, calibration, benchmark or evaluation behaviour changed,
and no stored results were regenerated.

- API: a model backend that cannot be reached or built (server down, missing `api_key_env`
  variable, optional dependency absent) now returns HTTP 503 `backend_unavailable` with the
  underlying reason, instead of a bare HTTP 500 with no body. Unexpected failures keep the
  documented error envelope and return an incident id while the traceback stays in the server log.
- `openai_compatible`: configuration mistakes raise `BackendConfigurationError`, which is both a
  `ValueError` (unchanged for existing callers) and a `BackendError` (catchable by serving layers).
- API: new `GET /api/v1/examples`, listing the demo questions the simulated backend can answer, so
  the web interface no longer has to hard-code them.
- Web: the playground shows the pipeline path actually taken (per attempt, escalation included)
  rather than a fixed diagram, explains what the simulated backend does, and offers the bundled
  demo questions as one-click examples.
- Web: switching configuration can no longer leave a model selected that the new configuration does
  not contain; requests time out instead of hanging; in-flight requests are cancelled on unmount.
- Web: error messages name the actual cause and give advice that matches it.
- Web: navigation labels are readable below 1000px wide (they were collapsed to bare numbers).
- Web: the quality–compute chart places labels from the data rather than from a hard-coded table of
  system names, so runs with other systems stay readable.
- Web: the trace record behind a response is reachable from the playground through the existing
  `GET /api/v1/traces/{id}` route, which nothing used before; it is fetched only when opened.
- Web: added a skip link, `aria-current` on the active navigation item, a visible focus ring, and
  `aria-hidden` on decorative marks. The metric grid no longer assumes exactly four cells.
- Web: chart geometry and trace derivation moved to `lib/chart-layout.ts` and `lib/trace.ts` and
  covered by tests (`npm test`, Node's own runner — no new dependency).
- `apps/web`: removed `agentRules: false`; Next's documented default keeps the tracked `AGENTS.md`
  current instead of leaving it stale.
- `scripts/run_web.sh` finds the interpreter in `$VIRTUAL_ENV`, `./.venv` or `PATH`, and honours
  `ROUTEGUARD_PYTHON`, instead of requiring `./.venv`.
- `scripts/publish_results.py` accepts `-h/--help` and reports directories that are not finished
  runs, instead of failing with a traceback.
- API: a request whose `Origin` is not in `ROUTEGUARD_CORS_ORIGINS` is logged as a warning. The
  browser discards such a response silently while the server records a plain 200, which makes a
  misconfigured origin very hard to diagnose from either side.
- Web: added an application icon; the app previously requested a favicon that did not exist.
- Web: the sidebar indicator now polls `GET /api/v1/health` and reports the real connection state
  and round-trip time. It was previously a green dot that was always green.
- Web: a live elapsed timer and spinner while a request is in flight. The API answers once, at the
  end, so this reports waiting time and does not pretend to track progress.
- Web: colour now carries meaning — pipeline stages are tinted by what they are, chart marks are
  coloured by system group with a legend and leader lines, difficulty and confidence are drawn as
  sequential 0–1 meters beside their numerals, and status badges carry a glyph so nothing depends
  on colour alone. The categorical palette is validated for colour-vision deficiency.
- - `routeguard demo` no longer forces port 7860: with no `--port` Gradio picks a free one and
  `GRADIO_SERVER_PORT` is honoured (it was silently overridden before, although the error message
  recommended it). A busy explicit port is reported as a message rather than a traceback.

## 0.1.0 (2026-09-19)

First public release.

- Pipeline: language identification (en/kk/ru/fa/ar, extensible), task classification (rules /
  learned / gold / none), difficulty estimation (heuristic, learned, neural, LLM judge), routing for
  any number of models (fixed, random, rules, threshold, learned, cost-aware, quality–cost, oracle),
  confidence estimation (token-probability family, self-consistency, semantic entropy, ensembles),
  per-model / per-language calibration, risk-controlled acceptance thresholds (including
  routing-conditional certification), deterministic verification (format, arithmetic, controlled
  benchmark code execution, grounding) and an optional judge, and an escalation engine (re-prompt, stronger model,
  retrieval, self-consistency, judge-select, tool).
- Backends: Hugging Face Transformers, OpenAI-compatible HTTP (vLLM, llama.cpp, Ollama, hosted APIs),
  and a simulated backend for tests. Persistent generation cache with lazy model loading.
- Benchmark protocol: pinned public datasets (Belebele, SIB-200, Global-MMLU, MGSM, MBPP, NQ-open,
  ARC; GSM8K optional); seeded, stratified, parallel-group-aware splits; cross-fitted difficulty
  features for routers; leakage assertions; multi-seed statistics; paired bootstrap and McNemar tests.
- Evaluation: quality, routing, reliability, efficiency and escalation metrics; realised risk of the
  acceptance rule; cost-matched mixture baseline; automatic failure taxonomy; Markdown/CSV/LaTeX
  tables; PNG/PDF figures.
- Optional modules: RAG reliability evaluation, tool-use failure taxonomy, Gradio dashboard,
  versioned FastAPI service, and Next.js research interface.
- Cluster support: sharded generation (`routeguard generate`), cache merging, SLURM and multi-GPU
  launchers.
- Reference experiments with Qwen3-0.6B/1.7B/8B (results and provenance in `docs/results/`).
