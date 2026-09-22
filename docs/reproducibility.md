# Reproducibility

## One command per experiment

```bash
routeguard benchmark --config experiments/baselines/main.yaml
```

writes a versioned directory `results/runs/<name>_<YYYYmmdd-HHMMSS>_<gitsha>/`:

| Path | Content |
|---|---|
| `config.yaml` | the fully resolved experiment config (after `extends` and defaults) |
| `manifest.json` | status (`running` / `completed` / `failed` + error), git commit and dirty flag, Python/platform/package versions, GPU, seeds, dataset summary and fingerprint, model specs, split sizes, fitted thresholds, calibration fallbacks, per-system timings, model weight memory and process-wide peak GPU memory, cache hits |
| `raw/<system>_seed<k>.jsonl` | one record per test item: every attempt, confidence, verification, routing decision, per-model outcomes, token/latency/cost accounting |
| `processed/metrics.json` | all metrics per system (per seed, mean ± std, by language, by category), paired comparisons, error-analysis counts |
| `processed/error_analysis.md` | failure taxonomy, counts, examples |
| `tables/*.md|csv|tex` | paper-ready tables |
| `figures/*.png|pdf` | figures |

`routeguard evaluate <run_dir>` recomputes every metric and table from `raw/` without running a
model, and `routeguard plot <run_dir>` regenerates the figures.

## Sources of randomness

| Source | Control |
|---|---|
| train/calibration/test partition | `seeds` (seed-specific, stratified, group-aware) |
| item subsample | seed-independent (hash of the item/parallel id) |
| sampled generations | request seed = hash(system seed, query id, purpose, sample index) |
| random router | hash(seed, query id) |
| scikit-learn models | `random_state = seed` |
| Python / NumPy / torch | `set_global_seed(seed)` per seed |

Greedy decoding is deterministic for a given batch composition. Batched bf16 inference can change
low-order bits between batch compositions. The generation cache removes this within a project:
each unique request is generated once and re-used by every system and seed.

## Generation cache

`cache.path` (SQLite). Keys include the backend identity (model id, revision, options that affect
outputs) and the full request. Delete the file to regenerate. Share the file to let others replay
a run exactly. Cached entries keep the measured latency and tokens, so replayed runs report the
original costs.

## Latency

- Batched Hugging Face generation reports **amortised** latency (batch wall time ÷ batch size)
  per request; the unamortised batch time is stored in the call's `extra`. Relative comparisons
  between systems are valid because all systems are measured the same way.
- For deployment-realistic per-request latency, set `options.batch_size: 1` or use an
  OpenAI-compatible server (vLLM, llama.cpp), where latency is measured per HTTP request.
- P50/P95 are over per-query totals (sum over all calls of the query).

## Compute and cost

`tflops` uses the standard forward-pass approximation of 2 × parameters × (input + output
tokens) (Kaplan et al., 2020), ignoring attention's sequence-length term. USD cost is computed
only from prices you configure. No prices are shipped, because they change.

## PyTorch kernels

Recent PyTorch versions route a few operations through JIT-compiled Triton kernels. These need a
C toolchain and Python headers at run time and can differ numerically across machines. The Hugging
Face backend keeps PyTorch on standard ATen kernels: it sets `TORCH_DISABLE_NATIVE_JIT=1` and, if
torch was already imported, deregisters the overrides. Set `TORCH_DISABLE_NATIVE_JIT=0` to opt in to
the JIT kernels.

## Statistics

- Seeds re-draw the partition, so seed std reflects split and sampling variability. Tables report
  mean ± std over seeds.
- Paired comparisons with the reference system use identical (seed, item) pairs: bootstrap 95% CI
  of the accuracy difference (5,000 resamples) and an exact McNemar test.
- All seeds and all systems are always reported; runs are never filtered.
