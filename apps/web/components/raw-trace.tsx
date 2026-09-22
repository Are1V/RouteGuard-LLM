"use client";

import { useState } from "react";
import { getTrace } from "@/lib/api";

/**
 * The full pipeline record for one request. Fetched only when opened, because it is
 * considerably larger than the summary the page already shows.
 */
export function RawTrace({ traceId }: { traceId: string }) {
  const [record, setRecord] = useState<string>("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load(event: React.SyntheticEvent<HTMLDetailsElement>) {
    if (!event.currentTarget.open || record || loading) return;
    setLoading(true);
    setError("");
    try {
      setRecord(JSON.stringify(await getTrace(traceId), null, 2));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load the trace record");
    } finally {
      setLoading(false);
    }
  }

  return (
    <details className="raw-trace" onToggle={load}>
      <summary>Raw trace record</summary>
      {loading && <p className="raw-trace-note">Loading…</p>}
      {error && <p className="raw-trace-note">{error}</p>}
      {record && <pre>{record}</pre>}
    </details>
  );
}
