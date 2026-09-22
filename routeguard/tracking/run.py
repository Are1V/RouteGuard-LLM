"""Lightweight experiment tracking: versioned run directories and manifests.

Each run writes::

    results/runs/<name>_<YYYYmmdd-HHMMSS>_<gitsha>/
        config.yaml          fully resolved experiment config
        manifest.json        environment, git state, data fingerprint, timings
        raw/*.jsonl          one record per (system, seed, test item)
        processed/           metrics.json, error_analysis.md, fitted thresholds
        tables/              .md / .csv / .tex
        figures/             .png / .pdf
"""

from __future__ import annotations

import datetime as dt
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any


def git_state(cwd: str | Path = ".") -> dict[str, Any]:
    def run(*args: str) -> str | None:
        try:
            out = subprocess.run(
                ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    commit = run("rev-parse", "HEAD")
    if commit is None:
        return {"commit": None, "dirty": None}
    status = run("status", "--porcelain")
    return {"commit": commit, "dirty": bool(status)}


def package_versions(
    names: tuple[str, ...] = (
        "routeguard-llm",
        "numpy",
        "scikit-learn",
        "scipy",
        "pydantic",
        "torch",
        "transformers",
        "datasets",
    ),
) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for n in names:
        try:
            versions[n] = importlib.metadata.version(n)
        except importlib.metadata.PackageNotFoundError:
            versions[n] = None
    return versions


def environment() -> dict[str, Any]:
    env: dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": package_versions(),
        "argv": sys.argv,
    }
    if "torch" in sys.modules:
        torch = sys.modules["torch"]
        env["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            env["gpu"] = torch.cuda.get_device_name(0)
    return env


class RunDirectory:
    def __init__(self, root: str | Path, name: str, timestamp: dt.datetime | None = None):
        ts = (timestamp or dt.datetime.now()).strftime("%Y%m%d-%H%M%S")
        sha = (git_state().get("commit") or "nogit")[:7]
        self.path = Path(root) / f"{name}_{ts}_{sha}"
        suffix = 1
        while self.path.exists():
            self.path = Path(root) / f"{name}_{ts}_{sha}-{suffix}"
            suffix += 1
        for sub in ("raw", "processed", "tables", "figures"):
            (self.path / sub).mkdir(parents=True, exist_ok=True)

    def write_json(self, relative: str, data: Any) -> Path:
        p = self.path / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return p

    def write_text(self, relative: str, text: str) -> Path:
        p = self.path / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p


class JsonlWriter:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = self.path.open("w", encoding="utf-8")

    def write(self, record: dict[str, Any]) -> None:
        self._f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def close(self) -> None:
        self._f.close()

    def __enter__(self) -> JsonlWriter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
