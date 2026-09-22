"""Subprocess execution of model-generated Python code.

.. warning::
   This is a *robustness* boundary, not a *security* boundary. Code runs in a
   separate interpreter (``python -I``) in a temporary directory with a timeout
   and CPU/memory rlimits, which prevents hangs and runaway memory use but does
   not stop malicious code from touching the file system or network. Run
   untrusted benchmarks inside a container or VM (see docs/benchmarks.md).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecutionResult:
    passed: bool
    timed_out: bool
    returncode: int | None
    stderr: str


def _limits(memory_mb: int, cpu_s: int) -> None:  # pragma: no cover - runs in child
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 2**20, memory_mb * 2**20))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))


def run_python(
    code: str, tests: list[str] | None = None, timeout_s: float = 10.0, memory_mb: int = 1024
) -> ExecutionResult:
    """Execute ``code`` followed by ``tests`` (assert statements); pass iff exit code 0."""
    program = code + "\n\n" + "\n".join(tests or []) + "\n"
    with tempfile.TemporaryDirectory(prefix="routeguard_exec_") as tmp:
        path = Path(tmp) / "program.py"
        path.write_text(program, encoding="utf-8")
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": "0"}
        preexec = None
        if sys.platform.startswith("linux"):

            def preexec() -> None:
                _limits(memory_mb, int(timeout_s) + 1)

        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(path)],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                preexec_fn=preexec,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(False, True, None, "timeout")
    return ExecutionResult(proc.returncode == 0, False, proc.returncode, proc.stderr[-2000:])
