import type { ReactNode } from "react";

export function Metric({
  label,
  value,
  note,
  meter,
}: {
  label: string;
  value: string | number | null | undefined;
  note?: string;
  /** An optional 0–1 bar shown under the value; the numeral stays authoritative. */
  meter?: ReactNode;
}) {
  const shown = value === null || value === undefined ? "Unavailable" : value;
  return (
    <div className="metric">
      <span>{label}</span>
      <strong className={shown === "Unavailable" ? "unavailable" : ""}>{shown}</strong>
      {meter}
      {note && <small>{note}</small>}
    </div>
  );
}

export function formatPercent(value: number | null | undefined, digits = 1) {
  return value === null || value === undefined ? null : `${(value * 100).toFixed(digits)}%`;
}

export function formatNumber(value: number | null | undefined, digits = 2) {
  return value === null || value === undefined ? null : value.toFixed(digits);
}
