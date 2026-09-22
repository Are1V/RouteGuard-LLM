"""Deterministic seeding helpers."""

from __future__ import annotations

import hashlib
import os
import random
import sys

import numpy as np


def set_global_seed(seed: int) -> None:
    """Seed Python, NumPy and, if it is already imported, PyTorch.

    PyTorch is deliberately not imported here: importing it has side effects (kernel
    registration) that the Hugging Face backend needs to control, and sampled generations
    are seeded explicitly per request anyway.
    """
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    torch = sys.modules.get("torch")
    if torch is None:
        return
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def derive_seed(*parts: object) -> int:
    """Stable 31-bit seed derived from arbitrary parts (independent of PYTHONHASHSEED)."""
    h = hashlib.sha256("\x1f".join(map(str, parts)).encode("utf-8")).digest()
    return int.from_bytes(h[:4], "little") & 0x7FFFFFFF


def stable_hash(*parts: object, length: int = 16) -> str:
    return hashlib.sha256("\x1f".join(map(str, parts)).encode("utf-8")).hexdigest()[:length]
