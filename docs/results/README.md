# Published results

Processed outputs of the reference experiments: Qwen3-0.6B / 1.7B / 8B, bf16, Hugging Face
Transformers, one NVIDIA GB10 GPU. Each folder has `tables/` (Markdown, CSV, LaTeX), the key
`figures/` (PNG, PDF), processed `metrics.json`, and a `PROVENANCE.json` with the run id, seeds,
data fingerprint and models. They were copied from `results/runs/<run>/` by
`scripts/publish_results.py`. The API uses these files when raw run directories are absent. The raw
per-example records stay in the run directories (git-ignored); regenerate them with the
commands below.

| Folder | Experiment config | What it answers |
|---|---|---|
| `main/` | `experiments/baselines/main.yaml` | RouteGuard vs fixed-model, random, rule, difficulty, learned, cascade routing and the oracle |
| `routing/` | `experiments/routing/router_comparison.yaml` | Routers and difficulty estimators without escalation; cost-aware τ and quality–cost λ sweeps |
| `risk_sweep/` | `experiments/routing/risk_sweep.yaml` | Sensitivity to the target risk α; routing-conditional vs unconditional risk control |
| `ablations/` | `experiments/ablations/routeguard_ablations.yaml` | One component removed or swapped at a time |
| `sampling_confidence/` | `experiments/ablations/sampling_confidence.yaml` | Self-consistency and semantic entropy (one seed; n=4 samples) |
| `multilingual/` | `experiments/multilingual/multilingual_routing.yaml` | English-only vs multilingual router training; per-language calibration |
| `belebele_rag/` | `experiments/rag/belebele_rag.yaml` | Retrieval vs generation failures by language |
| `tool_use_hf/` | `experiments/tools/tool_use_hf.yaml` | Tool-use failure taxonomy (10-case probe) |

Reproduce: `routeguard benchmark --config <config>` (or `routeguard rag-eval` / `routeguard
tool-eval`), then `python scripts/publish_results.py results/runs/<run>`.
