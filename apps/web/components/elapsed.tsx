"use client";

import { useEffect, useState } from "react";

/**
 * Wall-clock time since the request was sent. The API returns one response at the
 * end, so this reports how long the caller has been waiting — it is not a progress
 * bar and does not claim to know how far the pipeline has got.
 */
export function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(() => performance.now());

  useEffect(() => {
    const id = setInterval(() => setNow(performance.now()), 100);
    return () => clearInterval(id);
  }, []);

  return <span className="elapsed">{((now - since) / 1000).toFixed(1)}s</span>;
}
