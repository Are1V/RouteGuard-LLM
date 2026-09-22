export type ModelInfo = {
  name: string;
  backend: string;
  model_id: string;
  params_b: number;
  simulated: boolean;
  max_new_tokens: number;
  priced: boolean;
};

export type ConfigurationInfo = {
  id: string;
  name: string;
  models: string[];
  simulated: boolean;
  ready_for_inference: boolean;
};

/** Mirrors `HealthResponse` in apps/api/schemas.py. */
export type HealthResponse = {
  status: "ok" | "not_ready";
  version: string;
  simulated: boolean | null;
};

export type ExampleQuery = {
  query: string;
  answer_type: AnswerType;
  language: string;
  category: string;
};

/** Mirrors `InferenceRequest` in apps/api/schemas.py, which forbids unknown fields. */
export type InferenceRequest = {
  query: string;
  config: string;
  routing: "automatic" | "manual";
  model: string | null;
  language: string;
  answer_type: AnswerType;
  choices: string[] | null;
  verification: boolean;
  escalation: boolean;
};

export type AnswerType = "text" | "numeric" | "choice" | "code";

export type Attempt = {
  stage: string;
  model: string;
  raw_text: string;
  answer: string | null;
  confidence: {
    raw: number;
    method: string;
    calibrated: number | null;
    calibrated_label: string;
  } | null;
  verification: { passed: boolean | null; verifier: string; reason: string } | null;
  reliable: boolean | null;
  triggers: string[];
};

export type InferenceResult = {
  trace_id: string;
  simulated: boolean;
  query: string;
  detected_language: string;
  language_source: "detected" | "requested";
  language_confidence: number;
  task_category: string;
  task_confidence: number;
  difficulty_score: number;
  difficulty_label: string;
  selected_model: string;
  routing_strategy: string;
  routing_reason: string;
  attempts: Attempt[];
  escalated: boolean;
  escalation_reasons: string[];
  final_answer: string | null;
  final_model: string;
  totals: {
    input_tokens: number;
    output_tokens: number;
    latency_s: number;
    cost_usd: number | null;
    tflops: number | null;
    calls: number;
  };
};

export type ExperimentSummary = {
  id: string;
  name: string;
  description: string;
  started: string | null;
  simulated: boolean | null;
  systems: string[];
  seeds: number[];
  item_count: number | null;
  has_metrics: boolean;
  figure_count: number;
};

export type ExperimentDetail = {
  summary: ExperimentSummary;
  manifest: Record<string, unknown>;
  available_tables: string[];
  available_figures: string[];
};

export type Metric = { mean: number | null; std: number | null; n: number };
export type SystemMetrics = {
  group: string;
  fixed_model: string | null;
  metrics: Record<string, Metric>;
  by_language: Record<string, Record<string, Metric>>;
  acceptance_by_model: Record<string, unknown>;
};
export type ExperimentMetrics = {
  simulated: boolean;
  model_order: string[];
  reference_system: string;
  systems: Record<string, SystemMetrics>;
  paired_vs_reference: Record<string, unknown>;
  errors: {
    taxonomy?: Record<string, string>;
    per_system?: Record<string, Record<string, number>>;
    per_language?: Record<string, Record<string, number>>;
    n_records?: Record<string, number>;
    n_wrong?: Record<string, number>;
  };
};
