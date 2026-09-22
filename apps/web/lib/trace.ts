import type { InferenceResult } from "./types";

/** What a stage is, which drives both its colour and its label. */
export type StageKind =
  | "analysis"
  | "difficulty"
  | "route"
  | "attempt"
  | "escalate"
  | "accepted"
  | "escalated";

export type TraceStep = { kind: StageKind; label: string; detail: string };

/**
 * The path a request actually took. Every step is derived from the response, so an
 * escalated run shows more steps than an accepted one and nothing is asserted that
 * the API did not report.
 */
export function buildSteps(result: InferenceResult): TraceStep[] {
  const steps: TraceStep[] = [
    {
      kind: "analysis",
      label: "Analysis",
      detail: `${result.detected_language} \u00b7 ${result.task_category}`,
    },
    {
      kind: "difficulty",
      label: "Difficulty",
      detail: `${result.difficulty_score.toFixed(2)} ${result.difficulty_label}`,
    },
    {
      kind: "route",
      label: "Route",
      detail: `${result.routing_strategy} \u2192 ${result.selected_model}`,
    },
  ];

  result.attempts.forEach((attempt, index) => {
    steps.push({
      kind: index === 0 ? "attempt" : "escalate",
      label: index === 0 ? "Attempt" : "Escalate",
      detail: attempt.model,
    });
  });

  steps.push({
    kind: result.escalated ? "escalated" : "accepted",
    label: result.escalated ? "Escalated" : "Accepted",
    detail: result.final_model,
  });

  return steps;
}
