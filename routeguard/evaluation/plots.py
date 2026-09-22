"""Research figures (matplotlib, PNG + PDF).

Design rules applied throughout: one y-axis per chart, recessive grid, thin
marks, categorical colours in a fixed validated order and assigned by *system
group* (never cycled), a one-hue ordinal ramp for model tiers, direct labels
where points are few, and a watermark on every figure produced from the
simulated backend.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from routeguard.evaluation.calibration import reliability_bins

# Categorical palette in a fixed, colour-vision-deficiency-checked order (light surface).
CATEGORICAL = [
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#4a3aa7",
    "#e34948",
]
GROUP_STYLE = {
    "routeguard": (CATEGORICAL[0], "o"),
    "baseline": (CATEGORICAL[1], "s"),
    "ablation": (CATEGORICAL[2], "^"),
    "analysis": (CATEGORICAL[3], "D"),
    "oracle": ("#52514e", "*"),
}
ORDINAL_BLUE = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]
SEQUENTIAL_CMAP = "Blues"
TEXT = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
MIN_BIN_COUNT = 5

Record = dict[str, Any]


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 220,
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": TEXT,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "legend.frameon": False,
            "legend.fontsize": 8,
            "lines.linewidth": 2.0,
            "font.family": "DejaVu Sans",
        }
    )


class FigureWriter:
    def __init__(
        self,
        directory: str | Path,
        formats: Sequence[str] = ("png", "pdf"),
        simulated: bool = False,
    ):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.formats = list(formats)
        self.simulated = simulated
        self.written: list[str] = []
        _style()

    def save(self, fig: Figure, name: str) -> None:
        if self.simulated:
            fig.text(
                0.5,
                0.5,
                "SIMULATED BACKEND\nnot real model results",
                ha="center",
                va="center",
                fontsize=22,
                color="#e34948",
                alpha=0.18,
                rotation=25,
                transform=fig.transFigure,
                zorder=100,
            )
        fig.tight_layout()
        for fmt in self.formats:
            fig.savefig(self.dir / f"{name}.{fmt}", bbox_inches="tight")
        plt.close(fig)
        self.written.append(name)


def _finite(x: float) -> bool:
    return x is not None and not math.isnan(x)


# ------------------------------------------------------------------ trade-offs
def _label_points(ax: Axes, labels: list[str], pts: list[tuple[float, float]]) -> None:
    """Direct labels with a greedy vertical nudge so nearby labels do not overlap."""
    fig = ax.figure
    fig.canvas.draw()
    char_w = 7.5 * 0.55 * fig.dpi / 72  # approximate glyph width in display pixels
    line_h = 7.5 * 1.3 * fig.dpi / 72
    placed: list[tuple[float, float, float]] = []  # (x0, x1, y) of labels and markers
    for p in pts:  # markers are obstacles too
        mx, my = ax.transData.transform(p)
        placed.append((mx - 6, mx + 6, my))
    order = sorted(range(len(pts)), key=lambda i: (pts[i][1], pts[i][0]))
    for i in order:
        px, py = ax.transData.transform(pts[i])
        x0, x1 = px + 7, px + 8 + len(labels[i]) * char_w
        dy = 4.0
        while (
            any(x0 < qx1 and qx0 < x1 and abs(py + dy - qy) < line_h for qx0, qx1, qy in placed)
            and dy < 40 * line_h
        ):
            dy += line_h
        placed.append((x0, x1, py + dy))
        ax.annotate(
            labels[i],
            pts[i],
            textcoords="offset points",
            xytext=(6, dy * 72 / fig.dpi),
            fontsize=7.5,
            color=TEXT,
            arrowprops={"arrowstyle": "-", "color": GRID, "lw": 0.6} if dy > 4 else None,
        )


def pareto_front(points: list[tuple[float, float]]) -> list[int]:
    """Indices of points not dominated in (lower x, higher y)."""
    idx = sorted(range(len(points)), key=lambda i: (points[i][0], -points[i][1]))
    front, best = [], -math.inf
    for i in idx:
        if points[i][1] > best:
            front.append(i)
            best = points[i][1]
    return front


def tradeoff(
    fw: FigureWriter,
    summary: dict[str, dict[str, Any]],
    x_key: str,
    x_label: str,
    y_key: str,
    y_label: str,
    name: str,
    title: str,
    log_x: bool = False,
    frontier: Sequence[tuple[float, float]] | None = None,
) -> None:
    """Scatter of systems with their Pareto front; ``frontier`` optionally draws the
    cost-matched mixture of fixed-model systems as a reference line."""
    systems = [
        s
        for s, v in summary.items()
        if _finite(v["metrics"].get(x_key, {}).get("mean", math.nan))
        and _finite(v["metrics"].get(y_key, {}).get("mean", math.nan))
    ]
    if not systems:
        return
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    pts = []
    for s in systems:
        m = summary[s]["metrics"]
        x, y = m[x_key]["mean"], m[y_key]["mean"]
        xe, ye = m[x_key].get("std", 0.0), m[y_key].get("std", 0.0)
        color, marker = GROUP_STYLE.get(summary[s]["group"], (MUTED, "o"))
        hollow = summary[s]["group"] == "oracle"
        ax.errorbar(
            x,
            y,
            xerr=xe or None,
            yerr=ye or None,
            fmt=marker,
            ms=8,
            color=color,
            mfc="white" if hollow else color,
            mec=color,
            elinewidth=1,
            capsize=2,
            zorder=3,
        )
        pts.append((x, y))
    _label_points(ax, systems, pts)
    deployable = [i for i, s in enumerate(systems) if summary[s]["group"] != "oracle"]
    front = [deployable[i] for i in pareto_front([pts[i] for i in deployable])]
    if len(front) > 1:
        fx, fy = zip(*sorted(pts[i] for i in front), strict=True)
        ax.step(
            fx,
            fy,
            where="post",
            color=MUTED,
            lw=1,
            ls="--",
            zorder=2,
            label="Pareto front (deployable systems)",
        )
    handles = [
        plt.Line2D(
            [],
            [],
            marker=GROUP_STYLE[g][1],
            ls="",
            color=GROUP_STYLE[g][0],
            mfc="white" if g == "oracle" else GROUP_STYLE[g][0],
            ms=7,
            label=g + (" (not deployable)" if g == "oracle" else ""),
        )
        for g in GROUP_STYLE
        if any(summary[s]["group"] == g for s in systems)
    ]
    if len(front) > 1:
        handles.append(plt.Line2D([], [], color=MUTED, lw=1, ls="--", label="Pareto front"))
    if frontier:
        fx, fy = zip(*frontier, strict=True)
        ax.plot(fx, fy, color=CATEGORICAL[1], lw=1.2, ls=":", zorder=1)
        handles.append(
            plt.Line2D(
                [], [], color=CATEGORICAL[1], lw=1.2, ls=":", label="mixtures of fixed models"
            )
        )
    ax.legend(handles=handles, loc="lower right")
    if log_x:
        ax.set_xscale("log")
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title, loc="left")
    fw.save(fig, name)


# ------------------------------------------------------------------ breakdowns
def grouped_bars(
    fw: FigureWriter,
    data: dict[str, dict[str, float]],
    series: list[str],
    name: str,
    title: str,
    ylabel: str,
) -> None:
    """``data[group][series] -> value``; at most 4 series (fixed categorical order)."""
    groups = list(data)
    series = series[:4]
    if not groups or not series:
        return
    fig, ax = plt.subplots(figsize=(max(5.0, 0.9 * len(groups) * len(series) / 2 + 2), 3.8))
    width = 0.8 / len(series)
    x = np.arange(len(groups))
    for i, s in enumerate(series):
        vals = [data[g].get(s, math.nan) for g in groups]
        ax.bar(
            x + (i - (len(series) - 1) / 2) * width,
            vals,
            width * 0.92,
            color=CATEGORICAL[i],
            label=s,
            zorder=3,
        )
    ax.set_xticks(x, groups)
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, 1.0)
    ax.set_title(title, loc="left")
    ax.legend(ncol=min(4, len(series)), loc="upper left", bbox_to_anchor=(0, -0.12))
    fw.save(fig, name)


def single_bars(
    fw: FigureWriter,
    labels: list[str],
    values: list[float],
    name: str,
    title: str,
    xlabel: str,
    color: str = CATEGORICAL[0],
) -> None:
    if not labels:
        return
    fig, ax = plt.subplots(figsize=(6.0, 0.35 * len(labels) + 1.4))
    y = np.arange(len(labels))
    ax.barh(y, values, color=color, height=0.7, zorder=3)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    for yi, v in zip(y, values, strict=True):
        ax.text(v, float(yi), f" {v:.3g}", va="center", fontsize=7.5, color=TEXT)
    ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left")
    ax.grid(axis="y", visible=False)
    fw.save(fig, name)


def model_selection(
    fw: FigureWriter,
    shares: dict[str, list[float]],
    model_names: list[str],
    name: str = "model_selection_distribution",
) -> None:
    systems = list(shares)
    if not systems:
        return
    fig, ax = plt.subplots(figsize=(6.4, 0.34 * len(systems) + 1.6))
    left = np.zeros(len(systems))
    ramp = (
        ORDINAL_BLUE
        if len(model_names) <= len(ORDINAL_BLUE)
        else plt.cm.Blues(np.linspace(0.35, 0.95, len(model_names)))
    )
    step = max(1, len(ORDINAL_BLUE) // max(1, len(model_names)))
    for t, model in enumerate(model_names):
        vals = np.array([shares[s][t] for s in systems])
        color = (
            ramp[min(t * step, len(ramp) - 1)] if len(model_names) <= len(ORDINAL_BLUE) else ramp[t]
        )
        ax.barh(
            systems,
            vals,
            left=left,
            color=color,
            edgecolor="white",
            linewidth=1.5,
            label=f"tier {t}: {model}",
            zorder=3,
        )
        left += vals
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("share of test queries routed to each model (initial routing)")
    ax.set_title("Model selection distribution", loc="left")
    ax.grid(axis="y", visible=False)
    ax.legend(ncol=min(4, len(model_names)), loc="upper left", bbox_to_anchor=(0, -0.18))
    fw.save(fig, name)


# ----------------------------------------------------------------- reliability
def reliability_diagram(
    fw: FigureWriter, groups: dict[str, tuple[np.ndarray, np.ndarray]], name: str, title: str
) -> None:
    """Small multiples: one reliability diagram + confidence histogram per group."""
    groups = {k: v for k, v in groups.items() if len(v[0])}
    if not groups:
        return
    n = len(groups)
    cols = min(n, 3)
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(3.2 * cols, 3.1 * rows), squeeze=False)
    for ax, (label, (conf, corr)) in zip(axes.flat, groups.items(), strict=False):
        bins = reliability_bins(conf, corr, n_bins=10)
        centers = np.array([(b.lower + b.upper) / 2 for b in bins])
        counts = np.array([b.count for b in bins], dtype=float)
        filled = counts >= MIN_BIN_COUNT  # sparse bins are noise, not calibration evidence
        ax.bar(
            centers,
            counts / counts.sum(),
            width=0.09,
            color="#cde2fb",
            zorder=2,
            label="share of answers",
        )
        ax.plot([0, 1], [0, 1], color=MUTED, lw=1, ls="--", zorder=3, label="perfect calibration")
        ax.plot(
            centers[filled],
            [b.accuracy for b, f in zip(bins, filled, strict=True) if f],
            color=CATEGORICAL[0],
            marker="o",
            ms=5,
            lw=2,
            zorder=4,
            label="accuracy per confidence bin",
        )
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_title(f"{label} (n={len(conf)})", loc="left", fontsize=9)
        ax.set_xlabel("confidence")
        ax.set_ylabel("empirical accuracy")
    for ax in list(axes.flat)[n:]:
        ax.set_visible(False)
    axes.flat[0].legend(loc="upper left", fontsize=7)
    fig.text(
        0.01,
        -0.01,
        f"Accuracy is drawn for bins with at least {MIN_BIN_COUNT} answers; bars show the share "
        "of answers per bin; the dashed line is perfect calibration.",
        fontsize=7,
        color=MUTED,
    )
    fig.suptitle(title, x=0.01, ha="left", fontsize=10)
    fw.save(fig, name)


def confusion_heatmap(
    fw: FigureWriter, matrix: np.ndarray, labels: list[str], name: str, title: str
) -> None:
    fig, ax = plt.subplots(figsize=(1.1 * len(labels) + 2.2, 1.0 * len(labels) + 1.6))
    norm = matrix / np.maximum(1, matrix.sum(axis=1, keepdims=True))
    ax.imshow(norm, cmap=SEQUENTIAL_CMAP, vmin=0, vmax=1)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(
                j,
                i,
                f"{matrix[i, j]}\n{norm[i, j]:.0%}",
                ha="center",
                va="center",
                fontsize=7.5,
                color="white" if norm[i, j] > 0.55 else TEXT,
            )
    ax.set_xticks(range(len(labels)), labels)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("routed model")
    ax.set_ylabel("oracle (cheapest correct) model")
    ax.grid(False)
    ax.set_title(title, loc="left")
    fw.save(fig, name)


def difficulty_distribution(
    fw: FigureWriter, scores: dict[str, list[float]], name: str, title: str
) -> None:
    scores = {k: v for k, v in scores.items() if v}
    if not scores:
        return
    n = len(scores)
    cols = min(n, 5)
    fig, axes = plt.subplots(1, cols, figsize=(2.3 * cols + 0.6, 2.6), sharey=True, squeeze=False)
    for ax, (label, vals) in zip(axes.flat, scores.items(), strict=False):
        ax.hist(
            vals,
            bins=np.linspace(0, 1, 21),
            color=CATEGORICAL[0],
            edgecolor="white",
            linewidth=0.8,
            zorder=3,
            weights=np.ones(len(vals)) / len(vals),
        )
        ax.set_title(f"{label} (n={len(vals)})", loc="left", fontsize=9)
        ax.set_xlabel("difficulty score")
    axes.flat[0].set_ylabel("share of queries")
    fig.suptitle(title, x=0.01, ha="left", fontsize=10)
    fw.save(fig, name)
