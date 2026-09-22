import assert from "node:assert/strict";
import { test } from "node:test";
import { buildSteps } from "./trace.ts";
import type { Attempt, InferenceResult } from "./types.ts";

function attempt(model: string, reliable: boolean | null): Attempt {
  return {
    stage: "initial",
    model,
    raw_text: "",
    answer: "x",
    confidence: null,
    verification: null,
    reliable,
    triggers: [],
  };
}

function result(overrides: Partial<InferenceResult> = {}): InferenceResult {
  return {
    trace_id: "t",
    simulated: true,
    query: "q",
    detected_language: "en",
    language_source: "detected",
    language_confidence: 1,
    task_category: "math",
    task_confidence: 1,
    difficulty_score: 0.225,
    difficulty_label: "easy",
    selected_model: "small",
    routing_strategy: "threshold",
    routing_reason: "",
    attempts: [attempt("small", true)],
    escalated: false,
    escalation_reasons: [],
    final_answer: "391",
    final_model: "small",
    totals: {
      input_tokens: 1,
      output_tokens: 1,
      latency_s: 1,
      cost_usd: null,
      tflops: null,
      calls: 1,
    },
    ...overrides,
  };
}

test("an accepted single-attempt run ends in Accepted", () => {
  const steps = buildSteps(result());
  assert.deepEqual(
    steps.map((step) => step.label),
    ["Analysis", "Difficulty", "Route", "Attempt", "Accepted"],
  );
  assert.equal(steps.at(-1)?.kind, "accepted");
});

test("each extra attempt adds an Escalate step", () => {
  const steps = buildSteps(
    result({
      attempts: [attempt("small", false), attempt("medium", false), attempt("large", true)],
      escalated: true,
      final_model: "large",
    }),
  );
  assert.deepEqual(
    steps.map((step) => step.label),
    ["Analysis", "Difficulty", "Route", "Attempt", "Escalate", "Escalate", "Escalated"],
  );
  assert.equal(steps.at(-1)?.kind, "escalated");
});

test("steps report the values the API returned", () => {
  const steps = buildSteps(result());
  assert.equal(steps[0].detail, "en · math");
  assert.equal(steps[1].detail, "0.23 easy");
  assert.equal(steps[2].detail, "threshold → small");
});

test("each stage carries the kind that drives its colour", () => {
  const steps = buildSteps(
    result({ attempts: [attempt("small", false), attempt("large", true)], escalated: true }),
  );
  assert.deepEqual(
    steps.map((step) => step.kind),
    ["analysis", "difficulty", "route", "attempt", "escalate", "escalated"],
  );
});

test("a run with no attempts still reports its outcome", () => {
  const steps = buildSteps(result({ attempts: [] }));
  assert.deepEqual(
    steps.map((step) => step.label),
    ["Analysis", "Difficulty", "Route", "Accepted"],
  );
});
