"""Validated configuration schema.

Two kinds of YAML files exist:

* a **pipeline config** (``configs/*.yaml``) describes one RouteGuard system:
  models, analyzer, difficulty estimator, router, confidence, verification,
  escalation, and optional retrieval;
* an **experiment config** (``experiments/**/*.yaml``) references a pipeline
  config through ``pipeline: {extends: <path>}``, lists datasets, splits and seeds,
  and defines *systems* as overrides of that base pipeline.

Any mapping may contain ``extends: <relative path>``; the referenced file is
loaded first and the mapping is deep-merged on top (lists are replaced, not
concatenated). Unknown keys are rejected so typos fail loudly.

Path conventions: ``extends`` paths are relative to the YAML file that contains
them; dataset, corpus and cache paths are relative to the working directory
(run commands from the repository root).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------- pipeline
class ModelConfig(_Strict):
    name: str
    backend: str = "huggingface"
    model_id: str
    params_b: float = 0.0
    price_input_per_1k: float = 0.0
    price_output_per_1k: float = 0.0
    max_new_tokens: int = 512
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("options")
    @classmethod
    def _no_secrets(cls, v: dict[str, Any]) -> dict[str, Any]:
        for key in v:
            if key.lower() in {"api_key", "apikey", "token", "secret", "password"}:
                raise ValueError(
                    f"Do not put secrets in config files (options.{key}); "
                    "use options.api_key_env to name an environment variable"
                )
        return v


class AnalyzerConfig(_Strict):
    languages: list[str] = Field(default_factory=lambda: ["en", "kk", "ru", "fa", "ar"])
    task_classifier: Literal["rules", "learned", "given", "none"] = "rules"
    lexicon: str | None = None


class DifficultyConfig(_Strict):
    estimator: str = "heuristic"
    easy_below: float = 0.34
    hard_above: float = 0.67
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _ordered(self) -> DifficultyConfig:
        if not 0.0 <= self.easy_below <= self.hard_above <= 1.0:
            raise ValueError(
                "difficulty thresholds must satisfy 0 <= easy_below <= hard_above <= 1"
            )
        return self


class RouterConfig(_Strict):
    type: str = "threshold"
    options: dict[str, Any] = Field(default_factory=dict)


class ConfidenceConfig(_Strict):
    method: str = "mean_token_prob"  # "none" disables confidence estimation (ablation)
    options: dict[str, Any] = Field(default_factory=dict)
    calibration: Literal["none", "isotonic", "platt", "histogram"] = "isotonic"
    per_language: bool = False
    min_samples: int = 30


class VerificationConfig(_Strict):
    enabled: bool = True
    verifiers: list[str | dict[str, Any]] = Field(
        default_factory=lambda: list[str | dict[str, Any]](
            ["format", "arithmetic", "code_execution"]
        )
    )


class RiskControlConfig(_Strict):
    target_risk: float = Field(0.1, gt=0, lt=1)
    delta: float = Field(0.1, gt=0, lt=1)
    min_accepted: int = 10
    # Certify each model's *initial-answer* threshold only on the calibration items the router
    # would send to it. Routers select non-exchangeable subpopulations (e.g. hard queries for the
    # large model), under which thresholds certified on all items do not hold.
    conditional_on_routing: bool = False


class TriggerConfig(_Strict):
    confidence_below: float | None = 0.5
    risk_control: RiskControlConfig | None = None
    on_verification_failure: bool = True
    difficulty_above: float | None = None


class StageConfig(_Strict):
    type: str
    options: dict[str, Any] = Field(default_factory=dict)


class EscalationConfig(_Strict):
    enabled: bool = True
    triggers: TriggerConfig = Field(default_factory=TriggerConfig)
    stages: list[StageConfig] = Field(default_factory=lambda: [StageConfig(type="stronger_model")])
    max_stages: int = 3
    final_selection: Literal["last", "most_confident"] = "last"


class RetrievalConfig(_Strict):
    corpus: str
    k: int = 3
    k1: float = 1.5
    b: float = 0.75


class FitConfig(_Strict):
    """Which training-split examples supervised components may learn from."""

    train_languages: list[str] | None = Field(
        None, description="restrict router/difficulty training to these languages (None = all)"
    )


class CacheConfig(_Strict):
    enabled: bool = True
    path: str = ".routeguard_cache/generations.sqlite"


class PipelineConfig(_Strict):
    name: str = "routeguard"
    seed: int = 0
    models: list[ModelConfig]
    analyzer: AnalyzerConfig = Field(default_factory=AnalyzerConfig)
    difficulty: DifficultyConfig = Field(default_factory=DifficultyConfig)
    router: RouterConfig = Field(default_factory=RouterConfig)
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    escalation: EscalationConfig = Field(default_factory=EscalationConfig)
    retrieval: RetrievalConfig | None = None
    fit: FitConfig = Field(default_factory=FitConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)

    @model_validator(mode="after")
    def _consistent(self) -> PipelineConfig:
        names = [m.name for m in self.models]
        if len(set(names)) != len(names):
            raise ValueError(f"model names must be unique, got {names}")
        if not self.models:
            raise ValueError("at least one model is required")
        uses_retrieval = any(s.type == "retrieval" for s in self.escalation.stages)
        if uses_retrieval and self.retrieval is None:
            raise ValueError(
                "escalation stage 'retrieval' requires a top-level 'retrieval' section"
            )
        return self


# ------------------------------------------------------------------- experiment
class DatasetConfig(_Strict):
    loader: str
    name: str | None = None
    path: str | None = None
    limit: int | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class SplitConfig(_Strict):
    train: float = 0.4
    calibration: float = 0.2
    test: float = 0.4
    stratify_by: list[str] = Field(default_factory=lambda: ["language", "category"])

    @model_validator(mode="after")
    def _sum(self) -> SplitConfig:
        total = self.train + self.calibration + self.test
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"split fractions must sum to 1, got {total}")
        if self.test <= 0:
            raise ValueError("test fraction must be positive")
        return self


class ScoringConfig(_Strict):
    text_match: Literal["em", "f1", "contains"] = "contains"
    f1_threshold: float = 0.5
    code_timeout_s: float = 10.0


class SystemConfig(_Strict):
    name: str
    group: Literal["baseline", "routeguard", "ablation", "oracle", "analysis"] = "baseline"
    description: str = ""
    overrides: dict[str, Any] = Field(default_factory=dict)


FigureFormat = Literal["png", "pdf", "svg"]


class ReportConfig(_Strict):
    figures: bool = True
    tables: bool = True
    reference_system: str | None = None
    formats: list[FigureFormat] = Field(default_factory=lambda: list[FigureFormat](["png", "pdf"]))


class ExperimentConfig(_Strict):
    name: str
    description: str = ""
    seeds: list[int] = Field(default_factory=lambda: [0])
    output_dir: str = "results/runs"
    pipeline: dict[str, Any]
    data: list[DatasetConfig]
    splits: SplitConfig = Field(default_factory=SplitConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    systems: list[SystemConfig]
    report: ReportConfig = Field(default_factory=ReportConfig)

    @model_validator(mode="after")
    def _systems_valid(self) -> ExperimentConfig:
        names = [s.name for s in self.systems]
        if len(set(names)) != len(names):
            raise ValueError(f"system names must be unique, got {names}")
        # Validate every system eagerly so a typo fails before any model is run.
        pools = {tuple(m.name for m in self.system_pipeline(s).models) for s in self.systems}
        if len(pools) > 1:
            raise ValueError(
                "all systems of an experiment must share the same model pool "
                f"(routing metrics compare tiers); got {sorted(pools)}"
            )
        if self.report.reference_system and self.report.reference_system not in names:
            raise ValueError(
                f"report.reference_system '{self.report.reference_system}' is not a system"
            )
        return self

    def system_pipeline(self, system: SystemConfig) -> PipelineConfig:
        merged = deep_merge(self.pipeline, system.overrides)
        merged["name"] = system.name
        return PipelineConfig.model_validate(merged)


# ------------------------------------------------------------------------ loading
_KIND_KEYS = ("type", "method", "estimator")


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into ``base``.

    Lists are replaced. A mapping that switches component kind (a different
    ``type`` / ``method`` / ``estimator``) *replaces* the base mapping, so options of
    the previous component (e.g. threshold-router ``thresholds``) do not leak into
    the new one.
    """
    out = copy.deepcopy(base)
    for key, value in override.items():
        prev = out.get(key)
        if isinstance(value, dict) and isinstance(prev, dict):
            switches = any(k in value and k in prev and value[k] != prev[k] for k in _KIND_KEYS)
            out[key] = copy.deepcopy(value) if switches else deep_merge(prev, value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _resolve_extends(data: Any, base_dir: Path, seen: tuple[Path, ...] = ()) -> Any:
    if isinstance(data, dict):
        resolved = {
            k: _resolve_extends(v, base_dir, seen) for k, v in data.items() if k != "extends"
        }
        if "extends" in data:
            parent_path = (base_dir / data["extends"]).resolve()
            if parent_path in seen:
                raise ValueError(f"Circular 'extends' involving {parent_path}")
            parent = _resolve_extends(
                _read_yaml(parent_path), parent_path.parent, (*seen, parent_path)
            )
            return deep_merge(parent, resolved)
        return resolved
    if isinstance(data, list):
        return [_resolve_extends(v, base_dir, seen) for v in data]
    return data


def _read_yaml(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Read a YAML file and resolve ``extends`` references relative to it."""
    p = Path(path).resolve()
    data = _resolve_extends(_read_yaml(p), p.parent, (p,))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    return data


def load_pipeline_config(path: str | Path) -> PipelineConfig:
    return PipelineConfig.model_validate(load_yaml(path))


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    return ExperimentConfig.model_validate(load_yaml(path))


def is_experiment_config(data: dict[str, Any]) -> bool:
    return "systems" in data and "pipeline" in data


def dump_config(model: BaseModel) -> str:
    return yaml.safe_dump(model.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
