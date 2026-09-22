"use client";

import { useEffect, useMemo, useState } from "react";
import { formatNumber, formatPercent } from "@/components/metric";
import { EmptyState, ErrorState, PageHeader } from "@/components/shell";
import { getExperiments, getMetrics } from "@/lib/api";
import type { ExperimentMetrics, ExperimentSummary } from "@/lib/types";

/**
 * Dataset language codes. Iranian Persian and Dari are kept distinct on purpose:
 * collapsing them would hide a population the evaluation reports separately.
 */
const LANGUAGE_NAMES: Record<string, string> = {
  en: "English",
  kk: "Kazakh",
  ru: "Russian",
  pes_Arab: "Persian (Iranian)",
  prs_Arab: "Dari",
  fa: "Persian (dataset variety)",
};

const languageName = (code: string) => LANGUAGE_NAMES[code] ?? code;

export default function MultilingualPage() {
  const [runs, setRuns] = useState<ExperimentSummary[]>([]);
  const [selected, setSelected] = useState("");
  const [loaded, setLoaded] = useState<{ runId: string; metrics: ExperimentMetrics } | null>(null);
  const [system, setSystem] = useState("");
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const controller = new AbortController();
    getExperiments(controller.signal)
      .then(({ experiments }) => {
        setRuns(experiments);
        const withMetrics = experiments.filter((run) => run.has_metrics);
        const preferred =
          withMetrics.find((run) => run.id.startsWith("multilingual_")) ??
          withMetrics.find((run) => run.id.startsWith("main_")) ??
          withMetrics[0];
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
    getMetrics(selected, controller.signal)
      .then((metrics) => {
        setLoaded({ runId: selected, metrics });
        setError(null);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(cause);
      });
    return () => controller.abort();
  }, [selected]);

  const metrics = loaded?.runId === selected ? loaded.metrics : null;
  const loading = Boolean(selected) && !metrics && !error;
  const systemNames = useMemo(() => Object.keys(metrics?.systems ?? {}), [metrics]);

  // Derived so a run that has no "routeguard" system still shows something valid.
  const activeSystem = systemNames.includes(system)
    ? system
    : (systemNames.find((name) => name === "routeguard") ?? systemNames[0] ?? "");

  const languages = metrics?.systems[activeSystem]?.by_language ?? {};
  const languageCodes = Object.keys(languages);

  return (
    <div className="page">
      <PageHeader
        eyebrow="Languages"
        title="Multilingual results"
        description="Compare performance across supported languages."
        action={
          <div className="toolbar">
            <select
              aria-label="Experiment run"
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
            >
              <option value="">Select a run</option>
              {runs
                .filter((run) => run.has_metrics)
                .map((run) => (
                  <option key={run.id} value={run.id}>
                    {run.name}
                  </option>
                ))}
            </select>
            <select
              aria-label="System"
              value={activeSystem}
              disabled={!systemNames.length}
              onChange={(event) => setSystem(event.target.value)}
            >
              {systemNames.map((name) => (
                <option key={name} value={name}>
                  {name.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </div>
        }
      />
      {error != null && <ErrorState error={error} />}

      {loading ? (
        <div className="panel loading">Loading stored metrics…</div>
      ) : !languageCodes.length ? (
        <div className="panel">
          <EmptyState
            title="No language breakdown available"
            detail="Select a processed run containing by-language metrics. Nothing is synthesized when coverage is absent."
          />
        </div>
      ) : (
        <div className="content-grid">
          <section className="panel span-2">
            <div className="panel-head">
              <div>
                <h2>{activeSystem.replaceAll("_", " ")}</h2>
                <p>Quality and routing by language</p>
              </div>
            </div>
            <div className="panel-body table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Language population</th>
                    <th>Samples</th>
                    <th>Accuracy</th>
                    <th>Error AUROC</th>
                    <th>ECE</th>
                    <th>Tier 0</th>
                    <th>Tier 1</th>
                    <th>Tier 2</th>
                    <th>Escalation</th>
                  </tr>
                </thead>
                <tbody>
                  {languageCodes.map((code) => {
                    const values = languages[code];
                    return (
                      <tr key={code}>
                        <td>
                          <strong>{languageName(code)}</strong>
                          <br />
                          <small>{code}</small>
                        </td>
                        <td>{values.n?.mean == null ? "—" : Math.round(values.n.mean)}</td>
                        <td>{formatPercent(values.accuracy?.mean) ?? "—"}</td>
                        <td>{formatNumber(values.rel_auroc_error_detection?.mean) ?? "—"}</td>
                        <td>{formatNumber(values.rel_ece?.mean, 3) ?? "—"}</td>
                        <td>{formatPercent(values.share_tier_0?.mean) ?? "—"}</td>
                        <td>{formatPercent(values.share_tier_1?.mean) ?? "—"}</td>
                        <td>{formatPercent(values.share_tier_2?.mean) ?? "—"}</td>
                        <td>{formatPercent(values.escalation_rate?.mean) ?? "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel span-2">
            <div className="panel-body notice">
              Dataset coverage differs by language; compare like-for-like subsets when possible.
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
