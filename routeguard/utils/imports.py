"""Graceful handling of optional dependencies."""

from __future__ import annotations

import importlib
from types import ModuleType


class MissingDependencyError(ImportError):
    """Raised when an optional feature is used without its extra installed."""


def require(module: str, extra: str, feature: str) -> ModuleType:
    """Import ``module`` or raise an actionable error naming the pip extra to install."""
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise MissingDependencyError(
            f"{feature} requires the optional dependency '{module}'. "
            f"Install it with: pip install -e '.[{extra}]'"
        ) from exc
