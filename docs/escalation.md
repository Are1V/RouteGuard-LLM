# Verification and escalation

## Verifiers (`verification.verifiers`)

Verifiers run at inference time, so they never see gold answers. A verifier returns `passed=None`
when it does not apply, which is different from passing. The composite verifier runs them in
order and stops at the first failure, so an expensive judge is not called after a cheap check
has already failed.

| Name | Applies to | Check |
|---|---|---|
| `format` | all | response not truncated; an answer can be extracted; valid option letter; code parses and defines the required function; text answers are short-form |
| `arithmetic` | numeric | recomputes every binary `a op b = c` step written in the response (chain fragments such as `3 + 4 + 5 = 12` are skipped); Persian and Arabic-Indic digits are normalised |
| `code_execution` | code | runs the code against the *public* tests shown in the prompt (e.g. MBPP), in a subprocess with a timeout and CPU/memory limits |
| `grounding` | text + passage/evidence | share of answer tokens present in the passage/evidence ≥ `min_support` |
| `judge` | configurable | a second model answers Yes/No to "is this answer correct?"; charged to the query |

Deterministic checks are preferred, and the judge is off by default. LLM judges share failure
modes with the models they judge, so the metrics report verifier accuracy and false pass/fail
rates (`rel_verifier_*`) separately.

**Sandbox.** `verification/sandbox.py` is a robustness boundary, not a security boundary: it
prevents hangs and runaway memory use but not file-system or network access. Run untrusted code
benchmarks inside a container.

## Escalation policy (`escalation`)

An attempt is **unreliable** if any enabled trigger fires:

- `low_confidence`: confidence below the threshold. The threshold is `confidence_below`
  (fixed), or per-model and risk-controlled via `risk_control` (see `confidence.md`).
- `verification_failed`: an applicable verifier rejected the answer (`on_verification_failure`).
- `high_difficulty`: the *initial* answer came from a non-strongest model although the difficulty
  score exceeds `difficulty_above`.

Stages then run in order until an attempt is reliable or `max_stages` stages have produced
attempts. Stages that cannot apply return nothing and do not count, for example
`stronger_model` when the strongest model has already answered.

| Stage | What it does |
|---|---|
| `reprompt` | same model, "careful" prompt (slow down, check each step) |
| `stronger_model` | next stronger model (`target: next`) or the strongest (`target: strongest`) |
| `retrieval` | BM25 evidence from `retrieval.corpus` added to the prompt (`k`, `same_language`) |
| `self_consistency` | n samples, majority vote; vote share becomes the (raw) confidence |
| `judge_select` | a strong model sees earlier candidate answers and gives its own final answer |
| `tool` | calculator / unit-converter agent loop (numeric questions only) |

If no attempt is reliable, `final_selection: last` returns the last attempt with an answer, and
`most_confident` returns the attempt with the highest confidence.

```yaml
escalation:
  enabled: true
  triggers:
    confidence_below: null
    risk_control: {target_risk: 0.15, delta: 0.1}
    on_verification_failure: true
    difficulty_above: null
  stages:
    - {type: stronger_model}
    - {type: self_consistency, options: {n: 5, temperature: 0.7}}
  max_stages: 2
  final_selection: last
```

## What is tracked

For each query the record stores every attempt (stage, model, answer, raw/calibrated
confidence, verifier verdict, triggers), the escalation causes, and the cost of escalation
separately from the initial answer (`escalation_cost_usd`, `escalation_tflops`,
`escalation_latency_s`, `escalation_tokens`). The metrics then report:

- escalation rate, precision (share of escalations whose initial answer was wrong) and recall
  (share of wrong initial answers that were escalated);
- **corrected rate**: P(final correct | escalated, initial wrong);
- **harm rate**: P(final wrong | escalated, initial correct). Escalation can break correct answers;
- share of all initial errors corrected, and of initially correct answers broken;
- share of total cost spent on escalation.

## Adding a stage

Subclass `routeguard.escalation.EscalationStage`, implement `run(pipe, query, analysis,
attempts, ctx)`, generate through `pipe.attempt(...)` or `ctx.generate(...)` so the call is
charged, and register it with `routeguard.escalation.register_stage("name", Cls)`.
