import type {
  ConfigurationInfo,
  ExampleQuery,
  ExperimentDetail,
  ExperimentMetrics,
  ExperimentSummary,
  HealthResponse,
  InferenceRequest,
  InferenceResult,
  ModelInfo,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1";

/** Metadata reads are quick; a single inference may escalate through several models. */
const READ_TIMEOUT_MS = 15_000;
const INFERENCE_TIMEOUT_MS = 180_000;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ErrorEnvelope = { error?: { message?: string; code?: string } };

type RequestOptions = RequestInit & { timeoutMs?: number };

async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = READ_TIMEOUT_MS, signal, ...init } = options;
  const timeout = AbortSignal.timeout(timeoutMs);
  // Combine the caller's cancellation (unmount, superseded request) with the timeout.
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init.headers },
      cache: "no-store",
      signal: combined,
    });
  } catch (cause) {
    if (signal?.aborted) throw cause;
    if (timeout.aborted) {
      throw new ApiError(
        `The API did not respond within ${Math.round(timeoutMs / 1000)}s.`,
        0,
        "timeout",
      );
    }
    throw new ApiError(
      `Cannot reach the RouteGuard API at ${API_URL}. Is the backend running?`,
      0,
      "unreachable",
    );
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ErrorEnvelope;
    throw new ApiError(
      body.error?.message ?? `Request failed (HTTP ${response.status})`,
      response.status,
      body.error?.code,
    );
  }
  return response.json() as Promise<T>;
}

export const getHealth = (signal?: AbortSignal) =>
  api<HealthResponse>("/health", { signal, timeoutMs: 5_000 });

export const getConfigurations = (signal?: AbortSignal) =>
  api<ConfigurationInfo[]>("/configurations", { signal });

export const getModels = (config = "demo", signal?: AbortSignal) =>
  api<ModelInfo[]>(`/models?config=${encodeURIComponent(config)}`, { signal });

export const getExamples = (config = "demo", signal?: AbortSignal) =>
  api<ExampleQuery[]>(`/examples?config=${encodeURIComponent(config)}`, { signal });

/** The complete pipeline record behind an inference response, kept in memory by the API. */
export const getTrace = (id: string, signal?: AbortSignal) =>
  api<Record<string, unknown>>(`/traces/${encodeURIComponent(id)}`, { signal });

export const getExperiments = (signal?: AbortSignal) =>
  api<{ experiments: ExperimentSummary[] }>("/experiments", { signal });

export const getExperiment = (id: string, signal?: AbortSignal) =>
  api<ExperimentDetail>(`/experiments/${encodeURIComponent(id)}`, { signal });

export const getMetrics = (id: string, signal?: AbortSignal) =>
  api<ExperimentMetrics>(`/experiments/${encodeURIComponent(id)}/metrics`, { signal });

export const artifactUrl = (id: string, kind: "figures" | "tables", name: string) =>
  `${API_URL}/experiments/${encodeURIComponent(id)}/artifacts/${kind}/${encodeURIComponent(name)}`;

export const runInference = (body: InferenceRequest, signal?: AbortSignal) =>
  api<InferenceResult>("/inference", {
    method: "POST",
    body: JSON.stringify(body),
    timeoutMs: INFERENCE_TIMEOUT_MS,
    signal,
  });
