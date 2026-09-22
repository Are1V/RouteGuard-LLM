# Research methodology

## Research question

> Can a lightweight routing system reduce LLM inference cost and latency while maintaining
> answer quality, by predicting query difficulty, estimating the reliability of answers,
> verifying them, and escalating unreliable queries to stronger inference strategies?

## Objectives and how each is measured

| # | Objective | Measured by | Where |
|---|---|---|---|
| 1 | Difficulty can be predicted before generation | routing accuracy vs oracle tier; learned vs heuristic vs LLM-judge estimators | `routing` experiment, `routing` table, confusion matrix |
| 2 | Small models handle easy queries | per-model accuracy by difficulty bin; share routed to the smallest model | `accuracy_by_model`, `model_selection_distribution` |
| 3 | Hard queries reach stronger models | `incorrect_small_model_rate` (routed model wrong, a stronger one right) | `routing` table |
| 4 | Uncertainty detects unreliable answers | AUROC/AUPRC of initial confidence for detecting errors; ECE, Brier, AURC | `calibration` table, reliability diagrams |
| 5 | Escalation improves reliability | corrected rate, harm rate, share of initial errors corrected | `escalation` table |
| 6 | Routing reduces cost | mean TFLOPs (or USD) per query vs always-large at matched accuracy | `main_results`, Pareto figures |
| 7 | Quality/reliability/latency/cost trade-off | Pareto fronts over systems and λ/target sweeps | `pareto_*` figures, `routing` experiment |
| 8–9 | Routing differs across languages; multilingual queries are harder to route | per-language accuracy, routing errors, AUROC; language-related failures | `language_breakdown`, `language_reliability`, `multilingual` experiment |
| 10 | Behaviour across task categories | `by_category` metrics | `metrics.json` |

## Protocol (per seed, per system)

1. **Split** the item pool into train / calibration / test (40/20/40 in the core suite),
   stratified by source and language, keeping all translations of an item together.
2. **Train split**: run every pool model once (greedy) to obtain per-model correctness; fit the
   task classifier (if learned), the difficulty estimator and the router.
3. **Calibration split**: run every pool model once and compute raw confidence; fit per-model
   calibrators and (optionally) risk-controlled thresholds.
4. **Test split**: (a) run every model once for *analysis only* (oracle, routing accuracy,
   failure labels), then (b) run the full system on every query, charging every call.
5. **Score** deterministically; write per-item records; aggregate over seeds.

Fitted components record the ids they were trained on; the runner raises `LeakageError` if any is
a test id. Hyperparameters of RouteGuard (router target, risk level α, δ) are fixed *a priori* in
the configs; sweeps are reported as sweeps, never tuned on the test split.

## Baselines

Always-small / medium / large, random routing, rule-based routing, difficulty-threshold routing
(heuristic difficulty), a learned multiclass router, a **cascade** (always start small, escalate on
calibrated confidence; the classic alternative to routing), and the **oracle** (upper bound for
single-call routing; not deployable, never reported as a method).

## Ablations

Without confidence, without verification, without escalation, without task classification,
heuristic vs learned vs neural difficulty, raw fixed-threshold vs calibrated risk-controlled
escalation, and alternative confidence estimators (sequence log-prob, min-token prob, entropy;
self-consistency and semantic entropy in a separate one-seed run because they cost n extra
generations per answer). The multilingual study compares multilingual vs English-only router
training and global vs per-language calibration.

## Statistics

Mean ± standard deviation over seeds (seeds change the partition). Paired comparisons with the
reference system on identical (seed, item) pairs: bootstrap 95% CI of the accuracy difference and
an exact McNemar test. With several comparisons, treat p-values as descriptive (no multiplicity
correction is applied). Report effect sizes with CIs rather than p-values alone.

## Failure taxonomy

See `routeguard/evaluation/errors.py` (`TAXONOMY`) and `processed/error_analysis.md` in each run.
Labels are derived from observable signals: per-model outcomes (routing errors vs capability
limits), confidence and triggers (high-confidence errors, unnecessary escalations), verifier
verdicts (false pass / false fail), the escalation trace (failure, harm), parallel items
(language-related failures) and retrieval diagnostics (retrieval failure, unsupported answers).

## Threats to validity

- **Model family.** The reference experiments use one family (Qwen3). Conclusions about routing
  between families (and between local and API models) need their own runs.
- **Greedy oracle.** The oracle and the difficulty target use single greedy generations, so
  "cheapest correct model" is noisy near capability boundaries.
- **Benchmark contamination.** Public benchmarks may be in the models' pre-training data. This
  affects all systems equally but can inflate absolute accuracies.
- **Language coverage.** Kazakh and Dari have fewer tasks than English and Russian (see
  `multilingual.md`); per-language differences confound language with task mix unless compared
  within a dataset (e.g. Belebele or SIB-200, which are parallel).
- **Latency under batching** is amortised (see `reproducibility.md`).
- **Lexical grounding** in the RAG module is a proxy for entailment.
- **Compute estimates** (2 × params × tokens) ignore attention cost and hardware efficiency.

## Paper-ready outputs

Every run writes Markdown/CSV/LaTeX tables (main results, routing, efficiency, escalation,
calibration, language breakdown, language reliability, ablations, significance, error analysis)
and PNG/PDF figures (Pareto fronts, accuracy by model and language, reliability diagrams,
calibration by model, router confusion matrix, difficulty distribution, model selection
distribution, failure types).

## Possible paper direction

The framework is designed to support a study along the lines of *"RouteGuard: Reliability-Aware
Adaptive Routing for Cost-Efficient Multilingual LLM Inference"*. That title is a direction, not
a claim; any claim must come from runs like those above.
