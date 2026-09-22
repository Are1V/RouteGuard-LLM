/**
 * Geometry for the scatter chart, kept free of React so it can be tested directly.
 *
 * Label positions are derived from the data at render time rather than tuned per
 * system name, so a run whose systems differ from the reference study still gets
 * readable labels.
 */

export type Point = { label: string; x: number; y: number; group?: string };
export type Box = { left: number; right: number; top: number; bottom: number };

export const WIDTH = 720;
export const HEIGHT = 330;
export const PAD = { left: 62, right: 22, top: 22, bottom: 54 };

/** Vertical offsets tried in order; the first that clears everything placed wins. */
const OFFSETS = [-11, 17, -25, 31, -39];
const CHAR_WIDTH = 5.4; // 9px monospace
const LINE_HEIGHT = 11;
const DOT_RADIUS = 8;

export const readable = (label: string) => label.replaceAll("_", " ");

export const overlaps = (a: Box, b: Box) =>
  a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;

export type Scales = { sx: (x: number) => number; sy: (y: number) => number };

/** Accuracy is shown on a 0–1 axis; compute starts at 0 so magnitudes stay comparable. */
export function scalesFor(points: Point[]): Scales {
  const maxX = Math.max(...points.map((point) => point.x), 1);
  const minY = Math.min(...points.map((point) => point.y), 0);
  const maxY = Math.max(...points.map((point) => point.y), 1);
  return {
    sx: (x) => PAD.left + (x / maxX) * (WIDTH - PAD.left - PAD.right),
    sy: (y) =>
      HEIGHT -
      PAD.bottom -
      ((y - minY) / Math.max(maxY - minY, 0.01)) * (HEIGHT - PAD.top - PAD.bottom),
  };
}

export type PlacedLabel = {
  point: Point;
  px: number;
  py: number;
  dx: number;
  dy: number;
  anchor: "start" | "end";
};

/** Place each label near its dot, clearing both placed labels and every plotted point. */
export function placeLabels(points: Point[], { sx, sy }: Scales): PlacedLabel[] {
  const dots: Box[] = points.map((point) => ({
    left: sx(point.x) - DOT_RADIUS,
    right: sx(point.x) + DOT_RADIUS,
    top: sy(point.y) - DOT_RADIUS,
    bottom: sy(point.y) + DOT_RADIUS,
  }));
  const placed: Box[] = [];

  return points.map((point) => {
    const px = sx(point.x);
    const py = sy(point.y);
    const width = readable(point.label).length * CHAR_WIDTH;
    const anchor: "start" | "end" = px + width > WIDTH - PAD.right ? "end" : "start";
    const dx = anchor === "end" ? -10 : 10;
    const boxFor = (dy: number): Box => ({
      left: anchor === "end" ? px + dx - width : px + dx,
      right: anchor === "end" ? px + dx : px + dx + width,
      top: py + dy - LINE_HEIGHT,
      bottom: py + dy,
    });
    const dy =
      OFFSETS.find((candidate) => {
        const box = boxFor(candidate);
        return ![...placed, ...dots].some((other) => overlaps(box, other));
      }) ?? OFFSETS[0];
    placed.push(boxFor(dy));
    return { point, px, py, dx, dy, anchor };
  });
}

/** The box a placed label occupies, for tests and for callers that need bounds. */
export function labelBox({ point, px, py, dx, dy, anchor }: PlacedLabel): Box {
  const width = readable(point.label).length * CHAR_WIDTH;
  return {
    left: anchor === "end" ? px + dx - width : px + dx,
    right: anchor === "end" ? px + dx : px + dx + width,
    top: py + dy - LINE_HEIGHT,
    bottom: py + dy,
  };
}
