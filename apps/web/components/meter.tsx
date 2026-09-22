/**
 * A 0–1 magnitude drawn as a bar. One hue getting darker with the value, because
 * these quantities are ordered rather than categorical, and the numeral stays
 * beside it so the bar never carries the value on its own.
 */
export function Meter({
  value,
  label,
  tone = "sequential",
}: {
  value: number;
  label?: string;
  tone?: "sequential" | "confidence";
}) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className={`meter meter-${tone}`}>
      <div
        className="meter-track"
        role="meter"
        aria-valuenow={Number(value.toFixed(3))}
        aria-valuemin={0}
        aria-valuemax={1}
        aria-label={label}
      >
        <i style={{ width: `${Math.max(2, pct)}%`, "--v": value } as React.CSSProperties} />
      </div>
    </div>
  );
}
