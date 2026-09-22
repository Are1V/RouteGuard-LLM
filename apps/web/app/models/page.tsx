"use client";

import { useEffect, useState } from "react";
import { EmptyState, ErrorState, PageHeader } from "@/components/shell";
import { getConfigurations, getModels } from "@/lib/api";
import type { ConfigurationInfo, ModelInfo } from "@/lib/types";

export default function ModelsPage() {
  const [configs, setConfigs] = useState<ConfigurationInfo[]>([]);
  const [selected, setSelected] = useState("demo");
  const [loaded, setLoaded] = useState<{ configId: string; models: ModelInfo[] } | null>(null);
  const [error, setError] = useState<unknown>(null);

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

  useEffect(() => {
    const controller = new AbortController();
    getModels(selected, controller.signal)
      .then((models) => {
        setLoaded({ configId: selected, models });
        setError(null);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(cause);
      });
    return () => controller.abort();
  }, [selected]);

  const models = loaded?.configId === selected ? loaded.models : [];
  const loading = !models.length && !error;
  const config = configs.find((item) => item.id === selected);

  return (
    <div className="page">
      <PageHeader
        eyebrow="Models"
        title="Model configurations"
        description="Inspect the models available to each route."
        action={
          <div className="toolbar">
            <select
              aria-label="Configuration"
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
            >
              {configs.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>
        }
      />
      {error != null && <ErrorState error={error} />}

      {loading ? (
        <div className="panel loading">Loading configuration…</div>
      ) : !models.length ? (
        <div className="panel">
          <EmptyState
            title="No configured models"
            detail="The API did not return public model metadata for this configuration."
          />
        </div>
      ) : (
        <div className="content-grid">
          <section className="panel span-2">
            <div className="panel-head">
              <div>
                <h2>{config?.name ?? selected}</h2>
                <p>{models.length} configured model{models.length === 1 ? "" : "s"}</p>
              </div>
              <div className="badges">
                <span className={`badge ${config?.simulated ? "info" : "good"}`}>
                  {config?.simulated ? "Simulated" : "Real backend"}
                </span>
                <span className={`badge ${config?.ready_for_inference ? "good" : "bad"}`}>
                  {config?.ready_for_inference ? "Ready" : "Requires fitting"}
                </span>
              </div>
            </div>
          </section>

          {models.map((item, index) => (
            <article className="panel" key={item.name}>
              <div className="panel-head">
                <div>
                  <p className="eyebrow" style={{ marginBottom: 5 }}>
                    Tier {index}
                  </p>
                  <h2>{item.name}</h2>
                </div>
                <span className={`badge ${item.simulated ? "info" : "good"}`}>{item.backend}</span>
              </div>
              <div className="panel-body">
                <dl className="metadata">
                  <div>
                    <dt>Model ID</dt>
                    <dd>{item.model_id}</dd>
                  </div>
                  <div>
                    <dt>Parameters</dt>
                    <dd>{item.params_b ? `${item.params_b}B` : "Unavailable"}</dd>
                  </div>
                  <div>
                    <dt>Output limit</dt>
                    <dd>{item.max_new_tokens} tokens</dd>
                  </div>
                  <div>
                    <dt>Pricing</dt>
                    <dd>{item.priced ? "Configured" : "Unavailable"}</dd>
                  </div>
                </dl>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
