import { EmptyState } from "@/components/shell";
import {
  HEIGHT,
  PAD,
  type Point,
  WIDTH,
  placeLabels,
  readable,
  scalesFor,
} from "@/lib/chart-layout";

const TICKS = [0, 0.25, 0.5, 0.75, 1];

export function ScatterChart({
  points,
  xLabel,
  yLabel,
}: {
  points: Point[];
  xLabel: string;
  yLabel: string;
}) {
  if (!points.length) {
    return (
      <EmptyState
        title="No comparable systems"
        detail="This run has no systems reporting both accuracy and estimated compute."
      />
    );
  }

  const scales = scalesFor(points);
  const maxX = Math.max(...points.map((point) => point.x), 1);
  const minY = Math.min(...points.map((point) => point.y), 0);
  const maxY = Math.max(...points.map((point) => point.y), 1);
  const labels = placeLabels(points, scales);

  const groups = [...new Set(points.map((point) => point.group ?? "baseline"))];

  return (
    <div className="chart-wrap">
      <ul className="chart-legend">
        {groups.map((group) => (
          <li key={group} className={`group-${group}`}>
            <i aria-hidden="true" />
            {group.replaceAll("_", " ")}
          </li>
        ))}
      </ul>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`${yLabel} versus ${xLabel}`}>
        {TICKS.map((tick) => {
          const y = PAD.top + tick * (HEIGHT - PAD.top - PAD.bottom);
          return (
            <g key={`y-${tick}`}>
              <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y} y2={y} className="grid" />
              <text x={PAD.left - 9} y={y + 3} textAnchor="end">
                {(maxY - tick * (maxY - minY)).toFixed(2)}
              </text>
            </g>
          );
        })}
        {TICKS.map((tick) => (
          <text
            key={`x-${tick}`}
            x={PAD.left + tick * (WIDTH - PAD.left - PAD.right)}
            y={HEIGHT - PAD.bottom + 19}
            textAnchor="middle"
          >
            {(tick * maxX).toFixed(1)}
          </text>
        ))}
        <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={HEIGHT - PAD.bottom} className="axis" />
        <line
          x1={PAD.left}
          x2={WIDTH - PAD.right}
          y1={HEIGHT - PAD.bottom}
          y2={HEIGHT - PAD.bottom}
          className="axis"
        />
        {labels.map(({ point, px, py, dx, dy, anchor }) => {
          const focus = point.group === "routeguard";
          return (
            <g key={point.label}>
              <circle
                cx={px}
                cy={py}
                r={focus ? 7 : 5}
                className={`dot group-${point.group ?? "baseline"}${focus ? " focus-dot" : ""}`}
              >
                <title>
                  {readable(point.label)}: {point.y.toFixed(3)} at {point.x.toFixed(3)} TFLOPs
                </title>
              </circle>
              {/* When a label had to move to clear a neighbour, tie it back to its dot. */}
              {Math.abs(dy) > 14 && (
                <line
                  className="leader"
                  x1={px}
                  y1={py}
                  x2={px + dx}
                  y2={py + dy - (dy < 0 ? -3 : 4)}
                />
              )}
              <text x={px + dx} y={py + dy} textAnchor={anchor}>
                {readable(point.label)}
              </text>
            </g>
          );
        })}
        <text x={WIDTH / 2} y={HEIGHT - 12} className="axis-label">
          {xLabel}
        </text>
        <text transform={`translate(17 ${HEIGHT / 2}) rotate(-90)`} className="axis-label">
          {yLabel}
        </text>
      </svg>
    </div>
  );
}

export function Bars({ items }: { items: { label: string; value: number; detail?: string }[] }) {
  if (!items.length) {
    return <EmptyState title="No data" detail="This breakdown is not available for the run." />;
  }
  const max = Math.max(...items.map((item) => item.value), 0.001);
  return (
    <div className="bars">
      {items.map((item) => (
        <div className="bar-row" key={item.label}>
          <span title={item.label}>{item.label}</span>
          <div>
            <i style={{ width: `${Math.max(1, (item.value / max) * 100)}%` }} />
          </div>
          <strong>{item.detail ?? item.value.toFixed(2)}</strong>
        </div>
      ))}
    </div>
  );
}
