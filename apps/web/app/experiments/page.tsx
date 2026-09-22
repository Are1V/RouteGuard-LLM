"use client";

import { useEffect, useMemo, useState } from "react";
import { formatNumber, formatPercent } from "@/components/metric";
import { ScatterChart } from "@/components/simple-chart";
import { EmptyState, ErrorState, PageHeader } from "@/components/shell";
import { artifactUrl, getExperiment, getExperiments, getMetrics } from "@/lib/api";
import type { ExperimentDetail, ExperimentMetrics, ExperimentSummary } from "@/lib/types";

/** Figures worth showing inline; the rest stay available through the API. */
const HEADLINE_FIGURES = [
  "pareto_accuracy_vs_cost.png",
  "reliability_diagram.png",
];

function runLabel(run: ExperimentSummary) {
  const timestamp = run.id.split("_").slice(-2).join(" ");
  return run.name === run.id ? run.id : `${run.name} · ${timestamp}`;
}

export default function ExperimentsPage() {
  const [runs, setRuns] = useState<ExperimentSummary[]>([]);
  const [selected, setSelected] = useState("");
  // Keyed by run id so a stale response can never be shown against another run.
  const [loaded, setLoaded] = useState<{
    runId: string;
    metrics: ExperimentMetrics;
    detail: ExperimentDetail;
  } | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const controller = new AbortController();
    getExperiments(controller.signal)
      .then(({ experiments }) => {
        setRuns(experiments);
        const withMetrics = experiments.filter((run) => run.has_metrics);
        const preferred = withMetrics.find((run) => run.id.startsWith("main_")) ?? withMetrics[0];
        setSelected(preferred?.id ?? "");
        setError(null);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(cause);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    Promise.all([getMetrics(selected, controller.signal), getExperiment(selected, controller.signal)])
      .then(([metrics, detail]) => {
        setLoaded({ runId: selected, metrics, detail });
        setError(null);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(cause);
      });
    return () => controller.abort();
  }, [selected]);

  const metrics = loaded?.runId === selected ? loaded.metrics : null;
  const detail = loaded?.runId === selected ? loaded.detail : null;
  const loading = Boolean(selected) && !metrics && !error;

  const selectable = useMemo(() => runs.filter((run) => run.has_metrics), [runs]);
  const run = runs.find((item) => item.id === selected);

  const points = useMemo(() => {
    if (!metrics) return [];
    return Object.entries(metrics.systems).flatMap(([label, system]) => {
      const x = system.metrics.tflops_mean?.mean;
      const y = system.metrics.accuracy?.mean;
      return x == null || y == null ? [] : [{ label, x, y, group: system.group }];
    });
  }, [metrics]);

  const figures = detail?.available_figures.filter((name) => HEADLINE_FIGURES.includes(name)) ?? [];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Experiments"
        title="Compare runs"
        description="Review performance, cost, and reliability."
        action={
          <div className="toolbar">
            <select
              aria-label="Experiment run"
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
            >
              <option value="">Select a run</option>
              {selectable.map((item) => (
                <option key={item.id} value={item.id}>
                  {runLabel(item)}
                </option>
              ))}
            </select>
          </div>
        }
      />
      {error != null && <ErrorState error={error} />}

      {!selected ? (
        <div className="panel">
          <EmptyState
            title={runs.length ? "No experiment selected" : "No processed runs found"}
            detail={
              runs.length
                ? "Choose a run from the list above."
                : "Runs appear here once results/runs contains a manifest.json and processed/metrics.json. Produce one with: routeguard benchmark --config experiments/smoke/smoke.yaml"
            }
          />
        </div>
      ) : loading || !metrics ? (
        <div className="panel loading">Loading stored metrics…</div>
      ) : (
        <div className="content-grid">
          <section className="panel span-2">
            <div className="panel-head">
              <div>
                <h2>{run?.name}</h2>
                <p>{run?.description || "Stored run"}</p>
              </div>
              <span className={`badge ${metrics.simulated ? "info" : "good"}`}>
                {metrics.simulated ? "Simulated" : "Real model run"}
              </span>
            </div>
            <div className="panel-body">
              <dl className="metadata">
                <div>
                  <dt>Run ID</dt>
                  <dd>{selected}</dd>
                </div>
                <div>
                  <dt>Items</dt>
                  <dd>{run?.item_count ?? "Unavailable"}</dd>
                </div>
                <div>
                  <dt>Seeds</dt>
                  <dd>{run?.seeds.join(", ") || "Unavailable"}</dd>
                </div>
                <div>
                  <dt>Systems</dt>
                  <dd>{Object.keys(metrics.systems).length}</dd>
                </div>
                <div>
                  <dt>Model pool</dt>
                  <dd>{metrics.model_order.join(" → ")}</dd>
                </div>
              </dl>
            </div>
          </section>

          <section className="panel span-2">
            <div className="panel-head">
              <div>
                <h2>Quality–compute trade-off</h2>
                <p>Accuracy versus estimated compute</p>
              </div>
            </div>
            <div className="panel-body">
              <ScatterChart
                points={points}
                xLabel="Estimated compute / query (TFLOPs)"
                yLabel="Accuracy"
              />
            </div>
          </section>

          <section className="panel span-2">
            <div className="panel-head">
              <div>
                <h2>System comparison</h2>
                <p>Mean values across recorded seeds</p>
              </div>
            </div>
            <div className="panel-body table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>System</th>
                    <th>Group</th>
                    <th>Accuracy</th>
                    <th>TFLOPs</th>
                    <th>P50 latency</th>
                    <th>Calls</th>
                    <th>Escalation</th>
                    <th>Error AUROC</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(metrics.systems).map(([name, system]) => (
                    <tr key={name}>
                      <td>
                        <strong>{name.replaceAll("_", " ")}</strong>
                      </td>
                      <td>{system.group}</td>
                      <td>{formatPercent(system.metrics.accuracy?.mean) ?? "—"}</td>
                      <td>{formatNumber(system.metrics.tflops_mean?.mean) ?? "—"}</td>
                      <td>
                        {system.metrics.latency_p50_s?.mean == null
                          ? "—"
                          : `${system.metrics.latency_p50_s.mean.toFixed(2)} s`}
                      </td>
                      <td>{formatNumber(system.metrics.calls_mean?.mean) ?? "—"}</td>
                      <td>{formatPercent(system.metrics.escalation_rate?.mean) ?? "—"}</td>
                      <td>{formatNumber(system.metrics.rel_auroc_error_detection?.mean) ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {figures.length > 0 && (
            <section className="panel span-2">
              <div className="panel-head">
                <div>
                  <h2>Selected figures</h2>
                  <p>Key outputs from this run</p>
                </div>
              </div>
              <div className="panel-body figure-grid">
                {figures.map((name) => (
                  <figure key={name}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={artifactUrl(selected, "figures", name)}
                      alt={`${name.replace(".png", "").replaceAll("_", " ")} for run ${selected}`}
                      loading="lazy"
                    />
                    <figcaption>{name.replace(".png", "").replaceAll("_", " ")}</figcaption>
                  </figure>
                ))}
              </div>
            </section>
          )}

        </div>
      )}
    </div>
  );
}
