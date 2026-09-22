# Confidence, calibration, and risk control

## Model confidence is not probability of correctness

An estimator returns a **raw score** where larger means "more likely correct". Token
probabilities from LLMs are miscalibrated, and agreement rates depend on the sampling
temperature, so a raw score of 0.9 does not mean a 90% chance of being right. RouteGuard keeps
two fields:

- `ConfidenceResult.raw`: the estimator's native score;
- `ConfidenceResult.calibrated`: an estimate of the *empirical probability of correctness*,
  from a calibrator fitted on a held-out **calibration split** (disjoint from train and test).

Escalation thresholds apply to `calibrated` when available, otherwise to `raw`.
`rel_calibrated_fraction` in the metrics reports which one was used.

## Estimators (`confidence.method`)

| Method | Extra calls | Definition |
|---|---|---|
| `mean_token_prob` | 0 | arithmetic mean of generated-token probabilities |
| `sequence_logprob` | 0 | length-normalised sequence probability exp(mean log p) |
| `min_token_prob` | 0 | probability of the least likely token |
| `entropy` | 0 | 1 − mean normalised entropy of the top-k next-token distributions (k=5; an approximation of full-vocabulary entropy) |
| `self_consistency` | n | share of n sampled answers equal to the greedy answer |
| `semantic_entropy` | n | 1 − H(answer clusters)/log(n+1), clustering by answer equivalence (discrete semantic entropy) |
| `ensemble` | Σ | weighted mean of other estimators' raw scores (calibrate the result) |
| `none` | 0 | no confidence (ablation) |

Log-probability methods raise `MissingLogprobsError` if a backend returns no log-probabilities.
They never substitute a default value. Sampling methods charge their samples to the query
(`purpose: confidence_sample`).

**Limitation.** Answer equivalence for `semantic_entropy` uses normalisation (numbers, option
letters, code whitespace) and character n-gram similarity for free text, not an NLI model. This
is adequate for the short answers in the core suite and weaker for long-form answers.

## Calibration (`confidence.calibration`)

`isotonic` (default), `platt`, or `histogram`, fitted **per model** (raw scores from different
models live on different scales), and optionally per (model, language) with
`per_language: true`. Groups with fewer than `min_samples` examples fall back to the model
level. A model with too few examples, or with only one outcome class, gets a smoothed constant
(its base rate). Every fallback is recorded in the manifest (`fitted.<system>.calibration_fallbacks`).

## Risk-controlled acceptance (`escalation.triggers.risk_control`)

Instead of a hand-picked threshold, RouteGuard can choose, per model, the lowest threshold λ such
that with probability ≥ 1 − δ the error rate among answers with confidence ≥ λ is ≤ α:

1. On the calibration split, candidate thresholds are scanned from most to least conservative
   (fixed-sequence testing, as in Learn-then-Test, Angelopoulos et al., 2021).
2. For each λ, a one-sided Clopper–Pearson upper bound on the error rate among accepted answers
   is compared with α (cf. Geifman & El-Yaniv, 2017). The scan stops at the first failure.
3. The scan starts at the smallest coverage at which the target is attainable at all (n ≥
   log δ / log(1−α)). This depends only on counts, not labels, so the sequence stays fixed
   a priori.

```yaml
escalation:
  triggers:
    confidence_below: null
    risk_control: {target_risk: 0.15, delta: 0.1, min_accepted: 10}
```

### Routing breaks exchangeability, so condition on it

The guarantee holds for queries exchangeable with the calibration items. A router *selects*
queries: in the reference experiments the large model receives mostly queries predicted to be
hard. Thresholds certified on all calibration items were then violated on test. The error rate
among accepted 8B answers was 27% against a 15% target, while the cascade, which performs no
selection, stayed within its bound wherever a threshold could be certified (46% at α = 0.5). Setting

```yaml
risk_control: {target_risk: 0.15, delta: 0.1, conditional_on_routing: true}
```

certifies each model's **initial-answer** threshold only on the calibration items the router
would send to that model, so the certification population matches the test population. Answers
produced during escalation still use thresholds certified on all calibration items. Every report
includes an `acceptance` table with the realised error rate among accepted initial answers per
model, so violations are visible.

If no threshold can be certified, all answers from that model are escalated
(`valid: false` in the manifest). The guarantee is marginal over queries exchangeable with the
calibration split. **It does not hold under distribution shift**, for example for a language
that is absent from the calibration data. The multilingual experiment measures how far the
realised risk departs from the target per language.

## Metrics

`evaluation/calibration.py` implements ECE (10 equal-width bins), Brier score, AUROC and AUPRC
for *detecting incorrect answers* (positive class = incorrect; chance-level AUPRC = error rate),
the risk–coverage curve and AURC, and the data for reliability diagrams. Reliability metrics are
computed on the **initial** attempt, the signal escalation acts on, and appear in the metrics
as `rel_*`.
