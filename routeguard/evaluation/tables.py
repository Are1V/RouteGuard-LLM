"""Paper-ready tables in Markdown, CSV, and LaTeX (booktabs), from one definition."""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SIMULATED_NOTE = (
    "SIMULATED BACKEND - these numbers come from the reference-aware simulator "
    "and are NOT results of real language models."
)


@dataclass
class Table:
    name: str
    caption: str
    columns: list[str]
    rows: list[list[Any]] = field(default_factory=list)
    note: str = ""

    def add(self, *values: Any) -> None:
        if len(values) != len(self.columns):
            raise ValueError(
                f"Table {self.name}: expected {len(self.columns)} values, got {len(values)}"
            )
        self.rows.append(list(values))

    # ----------------------------------------------------------------- renderers
    def to_markdown(self) -> str:
        out = [f"**{self.caption}**", ""]
        if self.note:
            out += [f"> {self.note}", ""]
        out.append("| " + " | ".join(self.columns) + " |")
        out.append(
            "|" + "|".join("---" if i == 0 else "---:" for i in range(len(self.columns))) + "|"
        )
        out += ["| " + " | ".join(_fmt(v) for v in row) + " |" for row in self.rows]
        return "\n".join(out) + "\n"

    def to_csv(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(self.columns)
        for row in self.rows:
            w.writerow([_fmt(v, plain=True) for v in row])
        return buf.getvalue()

    def to_latex(self) -> str:
        spec = "l" + "r" * (len(self.columns) - 1)
        lines = [
            "\\begin{table}[t]",
            "\\centering",
            "\\small",
            f"\\caption{{{_tex(self.caption)}}}",
            f"\\label{{tab:{self.name}}}",
            f"\\begin{{tabular}}{{{spec}}}",
            "\\toprule",
            " & ".join(_tex(c) for c in self.columns) + " \\\\",
            "\\midrule",
        ]
        lines += [" & ".join(_tex(_fmt(v, latex=True)) for v in row) + " \\\\" for row in self.rows]
        lines += ["\\bottomrule", "\\end{tabular}"]
        if self.note:
            lines.append(f"\\\\[2pt]{{\\footnotesize {_tex(self.note)}}}")
        lines.append("\\end{table}")
        return "\n".join(lines) + "\n"

    def save(self, directory: str | Path) -> None:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{self.name}.md").write_text(self.to_markdown(), encoding="utf-8")
        (d / f"{self.name}.csv").write_text(self.to_csv(), encoding="utf-8")
        (d / f"{self.name}.tex").write_text(self.to_latex(), encoding="utf-8")


@dataclass(frozen=True)
class MeanStd:
    mean: float
    std: float
    n: int = 1
    digits: int = 3
    percent: bool = False


def _fmt(v: Any, plain: bool = False, latex: bool = False) -> str:
    if isinstance(v, MeanStd):
        if math.isnan(v.mean):
            return "–"
        scale = 100.0 if v.percent else 1.0
        digits = 1 if v.percent else v.digits
        m = f"{v.mean * scale:.{digits}f}"
        if v.n <= 1:
            return m
        s = f"{v.std * scale:.{digits}f}"
        if plain:
            return f"{m} ± {s}"
        return f"{m} $\\pm$ {s}" if latex else f"{m} ± {s}"
    if isinstance(v, float):
        return "–" if math.isnan(v) else f"{v:.3f}"
    return str(v)


def _tex(s: str) -> str:
    if "$\\pm$" in s:
        left, right = s.split("$\\pm$")
        return _tex(left) + "$\\pm$" + _tex(right)
    for a, b in (
        ("\\", "\\textbackslash{}"),
        ("&", "\\&"),
        ("%", "\\%"),
        ("_", "\\_"),
        ("#", "\\#"),
        ("±", "$\\pm$"),
        ("–", "--"),
    ):
        s = s.replace(a, b)
    return s
