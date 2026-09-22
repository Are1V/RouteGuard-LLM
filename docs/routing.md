# Difficulty estimation and routing

## Difficulty estimators (`difficulty.estimator`)

All estimators return a score in [0, 1] and a label (`easy` < `easy_below` ≤ `medium` ≤
`hard_above` < `hard`).

| Name | Baseline | How it works | Needs training |
|---|---|---|---|
| `heuristic` | A | `sigmoid(bias + Σ wᵢ · clip(featureᵢ))` over length, numbers, math operators, code, entities, step/constraint cues (en/ru/kk/fa), passage presence, non-Latin script. Weights are documented priors, not tuned on evaluation data. Override with `options.weights`. | no |
| `learned` | B | Query vector → classifier over the *cheapest-correct tier*; score = E[tier]/N. Classifier: `logistic_regression` (default), `random_forest`, `xgboost`. | train split |
| `neural` | C | Same target with a small MLP (scikit-learn). | train split |
| `llm_judge` | D | A pool model (default: cheapest) rates difficulty 1–10; the call is charged. | no |

**Difficulty target.** For a training query, the *cheapest-correct tier* is the index of the
cheapest model that answers it correctly, or N if none does. This defines difficulty relative to
the model pool, which is what routing needs. It assumes rough monotonicity (a query solved by a
small model is usually solved by larger ones), and greedy decoding makes it noisy for queries
near a model's capability boundary. The error analysis measures that noise directly
(`model_outcomes` in each record).

**Query vector.** Standardised hand features + one-hot *detected* language + one-hot *predicted*
category + a text embedding: hashed character n-grams by default (no download,
script-agnostic), or a multilingual sentence encoder
(`options: {embedder: sentence_transformer}`). Gold labels are never used as features.

## Routers (`router.type`)

| Name | Router | Decision rule |
|---|---|---|
| `fixed` | baseline | always `options.model` (always-small/medium/large) |
| `random` | 1 | uniform (or `options.weights`), deterministic per (seed, query) |
| `rules` | 2 | ordered human-readable rules on category / language / difficulty label; first match wins |
| `threshold` | 3 | split the difficulty score into N bins (`options.thresholds`, N−1 increasing values) |
| `learned` | 4 | multiclass classifier over the cheapest-correct tier; route to the argmax tier |
| `cost_aware` | 5 | per-model success predictors p_m(x); the **cheapest** model with p_m(x) ≥ `target` |
| `quality_cost` | 6 | argmax_m p_m(x) − λ·cost_m − μ·latency_m (`cost_weight`, `latency_weight`) |
| `oracle` | upper bound | cheapest model that is actually correct (not deployable) |

Rule syntax:

```yaml
router:
  type: rules
  options:
    default: cheapest
    rules:
      - {when: {difficulty: [hard]}, model: strongest}
      - {when: {category: [coding, math]}, model: tier:1}
      - {when: {language: [kk, fa]}, model: qwen3-8b}
```

**Costs.** A model's relative cost is its price for a nominal request (400 input / 200 output
tokens) if prices are configured, otherwise its estimated forward compute (2 × parameters ×
tokens). `quality_cost` normalises costs to [0, 1] by the most expensive model, so λ is
comparable across pools. Sweeping λ (or `target` for `cost_aware`) traces a quality/cost
frontier; see `experiments/routing/router_comparison.yaml`.

**Oracle.** Routes to the cheapest model that is correct on the test query, or the cheapest
model if none is. It bounds what *single-call* routing can achieve with a given pool. Escalation
with sampling (self-consistency) can exceed it, because it can find answers that no single greedy
call produces. It is marked `group: oracle`, drawn hollow in plots, and excluded from Pareto
fronts.

## Adding a router

Subclass `routeguard.router.base.BaseRouter`, implement `route(...)` (and `fit(...)` if
supervised, setting `requires_fit = True` and recording `trained_ids`), then add it to
`routeguard.router.ROUTERS`. The runner's leakage check reads `trained_ids`.
