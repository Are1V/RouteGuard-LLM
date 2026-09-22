import assert from "node:assert/strict";
import { test } from "node:test";
import {
  PAD,
  type Point,
  WIDTH,
  labelBox,
  overlaps,
  placeLabels,
  scalesFor,
} from "./chart-layout.ts";

/** The ten systems of the reference `main` run, which previously collided. */
const MAIN_RUN: Point[] = [
  { label: "always_large", x: 5.68, y: 0.805, group: "baseline" },
  { label: "always_medium", x: 1.07, y: 0.666, group: "baseline" },
  { label: "always_small", x: 0.31, y: 0.479, group: "baseline" },
  { label: "cascade", x: 6.53, y: 0.809, group: "baseline" },
  { label: "difficulty_threshold", x: 1.64, y: 0.621, group: "baseline" },
  { label: "learned_router", x: 0.74, y: 0.528, group: "baseline" },
  { label: "oracle", x: 1.32, y: 0.865, group: "oracle" },
  { label: "random", x: 2.3, y: 0.64, group: "baseline" },
  { label: "routeguard", x: 5.95, y: 0.806, group: "routeguard" },
  { label: "rule_based", x: 1.6, y: 0.617, group: "baseline" },
];

function dotBoxes(points: Point[]) {
  const { sx, sy } = scalesFor(points);
  return points.map((point) => ({
    left: sx(point.x) - 8,
    right: sx(point.x) + 8,
    top: sy(point.y) - 8,
    bottom: sy(point.y) + 8,
  }));
}

test("every point is labelled", () => {
  const placed = placeLabels(MAIN_RUN, scalesFor(MAIN_RUN));
  assert.equal(placed.length, MAIN_RUN.length);
  assert.deepEqual(
    placed.map((item) => item.point.label).sort(),
    MAIN_RUN.map((point) => point.label).sort(),
  );
});

test("no label overlaps another label", () => {
  const boxes = placeLabels(MAIN_RUN, scalesFor(MAIN_RUN)).map(labelBox);
  for (let i = 0; i < boxes.length; i += 1) {
    for (let j = i + 1; j < boxes.length; j += 1) {
      assert.ok(
        !overlaps(boxes[i], boxes[j]),
        `labels ${MAIN_RUN[i].label} and ${MAIN_RUN[j].label} overlap`,
      );
    }
  }
});

test("no label covers a plotted point", () => {
  const boxes = placeLabels(MAIN_RUN, scalesFor(MAIN_RUN)).map(labelBox);
  const dots = dotBoxes(MAIN_RUN);
  boxes.forEach((box, i) => {
    dots.forEach((dot, j) => {
      assert.ok(!overlaps(box, dot), `label ${MAIN_RUN[i].label} covers dot ${MAIN_RUN[j].label}`);
    });
  });
});

test("labels near the right edge anchor inward", () => {
  const placed = placeLabels(
    [{ label: "a_very_long_system_name_here", x: 1, y: 0.5 }],
    scalesFor([{ label: "a_very_long_system_name_here", x: 1, y: 0.5 }]),
  );
  assert.equal(placed[0].anchor, "end");
  assert.ok(labelBox(placed[0]).right <= WIDTH - PAD.right + 1);
});

test("placement does not depend on a known set of system names", () => {
  const renamed = MAIN_RUN.map((point, index) => ({ ...point, label: `system_${index}` }));
  const boxes = placeLabels(renamed, scalesFor(renamed)).map(labelBox);
  const dots = dotBoxes(renamed);
  boxes.forEach((box) => {
    dots.forEach((dot) => assert.ok(!overlaps(box, dot)));
  });
});

test("a single point is placed without error", () => {
  const one: Point[] = [{ label: "solo", x: 0.5, y: 0.5 }];
  assert.equal(placeLabels(one, scalesFor(one)).length, 1);
});
