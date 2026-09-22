"use client";

import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";

type State = { kind: "checking" | "live" | "down"; detail: string };

const POLL_MS = 15_000;

/**
 * Live backend state. This replaces a decorative indicator that was always green:
 * a reader can now tell at a glance whether the API is actually answering.
 */
export function ApiStatus() {
  const [state, setState] = useState<State>({ kind: "checking", detail: "Checking…" });

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;

    async function check() {
      const started = performance.now();
      try {
        const health = await getHealth(controller.signal);
        const ms = Math.round(performance.now() - started);
        setState({ kind: "live", detail: `API ${health.version} · ${ms} ms` });
      } catch {
        if (!controller.signal.aborted) {
          setState({ kind: "down", detail: "Backend unreachable" });
        }
      }
      if (!controller.signal.aborted) timer = setTimeout(check, POLL_MS);
    }

    check();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, []);

  const label =
    state.kind === "live" ? "Connected" : state.kind === "down" ? "Offline" : "Connecting";

  return (
    <div className={`api-status status-${state.kind === "checking" ? "idle" : state.kind}`}>
      <span className="status-dot" aria-hidden="true" />
      <span role="status">{label}</span>
      <small>{state.detail}</small>
    </div>
  );
}
