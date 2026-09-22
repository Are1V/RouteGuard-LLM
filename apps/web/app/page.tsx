"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Elapsed } from "@/components/elapsed";
import { Meter } from "@/components/meter";
import { Metric, formatNumber } from "@/components/metric";
import { RawTrace } from "@/components/raw-trace";
import { ErrorState, PageHeader } from "@/components/shell";
import { TraceSteps } from "@/components/trace-steps";
import { getConfigurations, getExamples, getModels, runInference } from "@/lib/api";
import type {
  AnswerType,
  ConfigurationInfo,
  ExampleQuery,
  InferenceResult,
  ModelInfo,
} from "@/lib/types";

const LANGUAGES = [
  ["auto", "Auto detect"],
  ["en", "English"],
  ["kk", "Kazakh"],
  ["ru", "Russian"],
  ["fa", "Iranian Persian"],
  ["prs_Arab", "Dari"],
];

const ANSWER_TYPES: [AnswerType, string][] = [
  ["text", "Text"],
  ["numeric", "Numeric"],
  ["choice", "Multiple choice"],
  ["code", "Code"],
];

export default function InferencePage() {
  const [configs, setConfigs] = useState<ConfigurationInfo[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [examples, setExamples] = useState<ExampleQuery[]>([]);
  const [config, setConfig] = useState("demo");
  const [query, setQuery] = useState("What is 17 multiplied by 23?");
  const [routing, setRouting] = useState<"automatic" | "manual">("automatic");
  const [model, setModel] = useState("");
  const [language, setLanguage] = useState("auto");
  const [answerType, setAnswerType] = useState<AnswerType>("numeric");
  const [choices, setChoices] = useState("");
  const [verification, setVerification] = useState(true);
  const [escalation, setEscalation] = useState(true);
  const [result, setResult] = useState<InferenceResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [startedAt, setStartedAt] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const inFlight = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getConfigurations(controller.signal)
      .then((items) => {
        setConfigs(items);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(cause);
      });
    return () => controller.abort();
  }, []);

  // Models and examples belong to the selected configuration and are reloaded with it.
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([getModels(config, controller.signal), getExamples(config, controller.signal)])
      .then(([modelList, exampleList]) => {
        setModels(modelList);
        setExamples(exampleList);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(cause);
      });
    return () => controller.abort();
  }, [config]);

  useEffect(() => () => inFlight.current?.abort(), []);

  const selectedConfig = useMemo(
    () => configs.find((item) => item.id === config),
    [configs, config],
  );

  // Derived rather than stored, so switching configuration can never leave a model
  // selected that the new configuration does not contain.
  const selectedModel = models.some((item) => item.name === model)
    ? model
    : (models[0]?.name ?? "");

  /** The simulated backend only has reference answers for the bundled questions. */
  const isKnownExample = useMemo(
    () => examples.some((item) => item.query === query.trim()),
    [examples, query],
  );

  const applyExample = useCallback((example: ExampleQuery) => {
    setQuery(example.query);
    setAnswerType(example.answer_type);
    setChoices("");
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (loading) return;
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    setStartedAt(performance.now());
    setLoading(true);
    setError(null);
    try {
      const response = await runInference(
        {
          query,
          config,
          routing,
          model: routing === "manual" ? selectedModel : null,
          language,
          answer_type: answerType,
          choices:
            answerType === "choice"
              ? choices
                  .split("\n")
                  .map((item) => item.trim())
                  .filter(Boolean)
              : null,
          verification,
          escalation,
        },
        controller.signal,
      );
      setResult(response);
    } catch (cause) {
      if (controller.signal.aborted) return;
      setError(cause);
    } finally {
      if (inFlight.current === controller) {
        inFlight.current = null;
        setLoading(false);
      }
    }
  }

  const unresolved =
    result !== null && (result.final_answer === null || result.final_answer === "unknown");

  return (
    <div className="page">
      <PageHeader
        eyebrow="Inference"
        title="Run a request"
        description="Route a prompt and inspect the result."
      />
      {error != null && <ErrorState error={error} />}

      <div className="workspace">
        <form className="panel" onSubmit={submit}>
          <div className="panel-head">
            <div>
              <h2>Request</h2>
              <p>Configure and submit</p>
            </div>
          </div>
          <div className="panel-body form-grid">
            {selectedConfig?.simulated && (
              <div className="notice">
                <strong>Demo mode.</strong> Choose a sample question for a complete trace.
              </div>
            )}

            <div className="field">
              <label htmlFor="query">Query</label>
              <textarea
                id="query"
                rows={5}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                required
                maxLength={20000}
              />
            </div>

            {examples.length > 0 && (
              <ExamplePicker
                examples={examples}
                active={query.trim()}
                onPick={applyExample}
              />
            )}

            {answerType === "choice" && (
              <div className="field">
                <label htmlFor="choices">Choices · one per line</label>
                <textarea
                  id="choices"
                  rows={4}
                  value={choices}
                  onChange={(event) => setChoices(event.target.value)}
                  required
                />
              </div>
            )}

            <div className="field-row">
              <div className="field">
                <label htmlFor="config">Configuration</label>
                <select
                  id="config"
                  value={config}
                  onChange={(event) => setConfig(event.target.value)}
                >
                  {configs.map((item) => (
                    <option key={item.id} value={item.id} disabled={!item.ready_for_inference}>
                      {item.name}
                      {item.ready_for_inference ? "" : " (requires fitting)"}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="language">Language</label>
                <select
                  id="language"
                  value={language}
                  onChange={(event) => setLanguage(event.target.value)}
                >
                  {LANGUAGES.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="field-row">
              <div className="field">
                <label htmlFor="routing">Routing</label>
                <select
                  id="routing"
                  value={routing}
                  onChange={(event) => setRouting(event.target.value as "automatic" | "manual")}
                >
                  <option value="automatic">Automatic</option>
                  <option value="manual">Fixed model</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="model">Model</label>
                <select
                  id="model"
                  value={selectedModel}
                  disabled={routing === "automatic" || !models.length}
                  onChange={(event) => setModel(event.target.value)}
                >
                  {models.map((item) => (
                    <option key={item.name} value={item.name}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="field">
              <label htmlFor="answer-type">Expected answer format</label>
              <select
                id="answer-type"
                value={answerType}
                onChange={(event) => setAnswerType(event.target.value as AnswerType)}
              >
                {ANSWER_TYPES.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            <div className="switches">
              <label className="switch">
                <input
                  type="checkbox"
                  checked={verification}
                  onChange={(event) => setVerification(event.target.checked)}
                />
                Verification
              </label>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={escalation}
                  onChange={(event) => setEscalation(event.target.checked)}
                />
                Escalation
              </label>
            </div>

            <button className="button" type="submit" disabled={loading || !query.trim()}>
              {loading ? (
                <>
                  <span className="spinner" aria-hidden="true" />
                  Running pipeline… <Elapsed since={startedAt} />
                </>
              ) : (
                "Run inference"
              )}
            </button>
          </div>
        </form>

        <section className="panel" aria-live="polite" aria-busy={loading}>
          <div className="panel-head">
            <div>
              <h2>Execution trace</h2>
              <p>{result ? `Trace ${result.trace_id.slice(0, 12)}` : "No request has been run"}</p>
            </div>
            {result && (
              <span className={`badge ${result.simulated ? "info" : "good"}`}>
                {result.simulated ? "Simulated" : "Real backend"}
              </span>
            )}
          </div>

          {loading && !result ? (
            <div className="loading">
              <span className="spinner" aria-hidden="true" />
              Running the pipeline… <Elapsed since={startedAt} />
            </div>
          ) : !result ? (
            <div className="empty-state">
              <span>→</span>
              <h3>No trace yet</h3>
              <p>Submit a request to see the route and result.</p>
            </div>
          ) : (
            <div className="panel-body">
              <TraceSteps result={result} />

              <div className="answer-block">
                <small>Final answer · {result.final_model}</small>
                <p>{result.final_answer ?? "No answer could be extracted"}</p>
              </div>

              {unresolved && result.simulated && !isKnownExample && (
                <div className="notice" style={{ marginTop: 12 }}>
                  Demo mode only answers the sample questions. Choose one above or connect a model.
                </div>
              )}

              <div className="metric-grid" style={{ marginTop: 16 }}>
                <Metric
                  label="Language"
                  value={result.detected_language}
                  note={
                    result.language_source === "detected"
                      ? `${(result.language_confidence * 100).toFixed(0)}% detector confidence`
                      : "explicit request override"
                  }
                />
                <Metric label="Task" value={result.task_category} />
                <Metric
                  label="Difficulty"
                  value={formatNumber(result.difficulty_score, 3)}
                  note={result.difficulty_label}
                  meter={<Meter value={result.difficulty_score} label="Predicted difficulty" />}
                />
                <Metric
                  label="Initially routed"
                  value={result.selected_model}
                  note={result.routing_strategy}
                />
              </div>

              <div className="attempt-list">
                {result.attempts.map((attempt, index) => (
                  <article className="attempt" key={`${attempt.stage}-${index}`}>
                    <div className="attempt-head">
                      <h3>
                        Attempt {index + 1} · {attempt.stage.replaceAll("_", " ")}
                      </h3>
                      <span className="badge">{attempt.model}</span>
                    </div>
                    <p>{attempt.raw_text}</p>
                    {attempt.confidence && (
                      <Meter
                        value={attempt.confidence.raw}
                        label={`Raw confidence for attempt ${index + 1}`}
                        tone="confidence"
                      />
                    )}
                    <div className="badges">
                      <span className="badge">
                        raw confidence:{" "}
                        {attempt.confidence ? attempt.confidence.raw.toFixed(3) : "unavailable"}
                      </span>
                      <span className="badge">
                        calibrated: {attempt.confidence?.calibrated?.toFixed(3) ?? "unavailable"}
                      </span>
                      <span className={`badge ${verificationTone(attempt.verification?.passed)}`}>
                        verification: {verificationLabel(attempt.verification?.passed)}
                      </span>
                      {attempt.triggers.map((trigger) => (
                        <span className="badge bad" key={trigger}>
                          {trigger.replaceAll("_", " ")}
                        </span>
                      ))}
                    </div>
                  </article>
                ))}
              </div>

              <div className="metric-grid" style={{ marginTop: 16 }}>
                <Metric label="Latency" value={`${result.totals.latency_s.toFixed(2)} s`} />
                <Metric
                  label="Tokens"
                  value={`${result.totals.input_tokens} in · ${result.totals.output_tokens} out`}
                  note={`${result.totals.calls} model call${result.totals.calls === 1 ? "" : "s"}`}
                />
                <Metric
                  label="Compute"
                  value={
                    result.totals.tflops === null
                      ? null
                      : `${result.totals.tflops.toFixed(3)} TFLOPs`
                  }
                  note="estimated"
                />
                <Metric
                  label="Monetary cost"
                  value={
                    result.totals.cost_usd === null
                      ? null
                      : `$${result.totals.cost_usd.toFixed(5)}`
                  }
                  note={result.totals.cost_usd === null ? "no pricing configured" : undefined}
                />
              </div>

              <RawTrace traceId={result.trace_id} />
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function ExamplePicker({
  examples,
  active,
  onPick,
}: {
  examples: ExampleQuery[];
  active: string;
  onPick: (example: ExampleQuery) => void;
}) {
  const [language, setLanguage] = useState("en");
  const languages = useMemo(
    () => Array.from(new Set(examples.map((item) => item.language))),
    [examples],
  );
  const shown = useMemo(
    () => examples.filter((item) => item.language === language).slice(0, 6),
    [examples, language],
  );

  return (
    <div className="field">
      <div className="example-head">
        <span className="field-label">Demo questions</span>
        <select
          aria-label="Example language"
          value={language}
          onChange={(event) => setLanguage(event.target.value)}
        >
          {languages.map((code) => (
            <option key={code} value={code}>
              {code}
            </option>
          ))}
        </select>
      </div>
      <div className="chips">
        {shown.map((example) => (
          <button
            type="button"
            key={example.query}
            className={`chip ${example.query === active ? "active" : ""}`}
            onClick={() => onPick(example)}
            title={`${example.category} · ${example.answer_type}`}
          >
            {example.query}
          </button>
        ))}
      </div>
    </div>
  );
}

function verificationLabel(passed: boolean | null | undefined) {
  if (passed === true) return "passed";
  if (passed === false) return "failed";
  return "not applicable";
}

function verificationTone(passed: boolean | null | undefined) {
  if (passed === true) return "good";
  if (passed === false) return "bad";
  return "";
}
