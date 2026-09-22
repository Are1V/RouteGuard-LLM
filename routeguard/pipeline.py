"""The RouteGuard inference pipeline.

``query -> analyze -> estimate difficulty -> route -> generate -> confidence ->
verify -> (escalate) -> final answer``, with every model call accounted for.

The pipeline itself never sees gold labels. Supervised components are fitted
through :meth:`RouteGuardPipeline.fit_*` with outcomes computed by the benchmark
runner on the training and calibration splits.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence

import numpy as np

from routeguard.analysis import LanguageDetector, QueryAnalyzer, build_task_classifier
from routeguard.analysis.task import LearnedTaskClassifier
from routeguard.answers import extract_answer
from routeguard.complexity import (
    DifficultyThresholds,
    TrainingExample,
    build_difficulty_estimator,
)
from routeguard.confidence import (
    CalibrationBank,
    CalibrationRecord,
    ConfidenceInput,
    ThresholdResult,
    build_confidence_estimator,
    risk_controlled_threshold,
)
from routeguard.config import PipelineConfig
from routeguard.context import CallContext
from routeguard.escalation import EscalationPolicy, build_stage
from routeguard.models import GenerationCache, ModelPool, ModelSpec
from routeguard.prompts import build_messages
from routeguard.rag.retriever import BM25Retriever
from routeguard.router import build_router
from routeguard.types import (
    Attempt,
    ConfidenceResult,
    GenerationOutput,
    Message,
    PipelineResult,
    Query,
    QueryAnalysis,
)
from routeguard.utils.seeding import derive_seed
from routeguard.verification import VerificationInput, build_verifier

logger = logging.getLogger(__name__)


def build_pool(config: PipelineConfig, cache: GenerationCache | None = None) -> ModelPool:
    specs = [ModelSpec(**m.model_dump()) for m in config.models]
    if cache is None and config.cache.enabled:
        cache = GenerationCache(config.cache.path)
    return ModelPool(specs, cache=cache)


class RouteGuardPipeline:
    def __init__(
        self,
        config: PipelineConfig,
        pool: ModelPool | None = None,
        retriever: BM25Retriever | None = None,
    ):
        self.config = config
        self.seed = config.seed
        self.pool = pool or build_pool(config)
        if [s.name for s in self.pool] != [m.name for m in config.models]:
            raise ValueError("The provided model pool does not match config.models")

        self.analyzer = QueryAnalyzer(
            LanguageDetector(config.analyzer.languages),
            build_task_classifier(
                config.analyzer.task_classifier, config.analyzer.lexicon, self.seed
            ),
        )
        d = config.difficulty
        self.difficulty = build_difficulty_estimator(
            d.estimator, DifficultyThresholds(d.easy_below, d.hard_above), d.options, self.seed
        )
        self.router = build_router(config.router.type, self.pool, config.router.options, self.seed)
        c = config.confidence
        self.confidence = (
            None if c.method == "none" else build_confidence_estimator(c.method, c.options)
        )
        self.calibration = None
        if self.confidence is not None and c.calibration != "none":
            self.calibration = CalibrationBank(c.calibration, c.per_language, c.min_samples)
        self.calibration_fitted = False
        v = config.verification
        self.verifier = build_verifier(v.verifiers) if v.enabled else None
        self.policy = EscalationPolicy(config.escalation, self.pool.strongest)
        self.stages = [build_stage(s.type, s.options) for s in config.escalation.stages]
        if retriever is None and config.retrieval is not None:
            r = config.retrieval
            retriever = BM25Retriever.from_jsonl(r.corpus, k1=r.k1, b=r.b)
        self.retriever = retriever

    # ------------------------------------------------------------------ fitting
    @property
    def needs_training_data(self) -> bool:
        return (
            isinstance(self.analyzer.task_classifier, LearnedTaskClassifier)
            or self.difficulty.requires_fit
            or self.router.requires_fit
        )

    @property
    def needs_calibration_data(self) -> bool:
        return self.calibration is not None or (
            self.confidence is not None and self.config.escalation.triggers.risk_control is not None
        )

    def fit_task_classifier(self, queries: Sequence[Query]) -> None:
        clf = self.analyzer.task_classifier
        if isinstance(clf, LearnedTaskClassifier):
            clf.fit(queries)

    def fit_difficulty_and_router(self, examples: list[TrainingExample]) -> None:
        """Fit the difficulty estimator, then the router on the estimator's own scores.

        ``fit.train_languages`` restricts training to some languages (by the *gold*
        language of the training item), e.g. to study English-only routing.
        """
        langs = self.config.fit.train_languages
        if langs:
            examples = [e for e in examples if (e.query.language or e.analysis.language) in langs]
            if not examples:
                raise ValueError(f"No training examples in languages {langs}")
        if self.difficulty.requires_fit:
            self.difficulty.fit(examples, self.pool.names)
        if self.router.requires_fit:
            scores = self._out_of_fold_difficulty(examples)
            for ex, score in zip(examples, scores, strict=True):
                ex.difficulty = score
            self.router.fit(examples)

    def _out_of_fold_difficulty(self, examples: list[TrainingExample], k: int = 5) -> list[float]:
        """Difficulty scores for the router's training examples.

        A supervised estimator scores its own training data optimistically, while at test
        time its scores are out-of-sample; a router trained on in-sample scores would learn
        from a feature distribution it never sees again. Supervised estimators are therefore
        cross-fitted: each example is scored by an estimator trained on the other folds.
        """
        if not self.difficulty.requires_fit or len(examples) < 2 * k:
            return [
                self.difficulty.estimate(e.query, e.analysis, self.context(e.query)).score
                for e in examples
            ]
        d = self.config.difficulty
        order = sorted(range(len(examples)), key=lambda i: derive_seed("oof", self.seed, i))
        scores = [0.0] * len(examples)
        for fold in range(k):
            held = set(order[fold::k])
            estimator = build_difficulty_estimator(
                d.estimator, DifficultyThresholds(d.easy_below, d.hard_above), d.options, self.seed
            )
            estimator.fit([e for i, e in enumerate(examples) if i not in held], self.pool.names)
            for i in held:
                e = examples[i]
                scores[i] = estimator.estimate(e.query, e.analysis, self.context(e.query)).score
        return scores

    def fit_calibration(self, records: Sequence[CalibrationRecord]) -> None:
        """Fit calibrators, then (optionally) risk-controlled per-model thresholds."""
        if self.calibration is not None:
            self.calibration.fit(records)
            self.calibration_fitted = True
        risk = self.config.escalation.triggers.risk_control
        if risk is None:
            return
        by_model: dict[str, list[tuple[float, bool]]] = defaultdict(list)
        routed: dict[str, list[tuple[float, bool]]] = defaultdict(list)
        for r in records:
            value = self._calibrate(r.model, r.language, r.raw)
            pair = (value if value is not None else r.raw, r.correct)
            by_model[r.model].append(pair)
            if r.routed:
                routed[r.model].append(pair)

        def certify(pairs: list[tuple[float, bool]]) -> ThresholdResult:
            conf = np.array([p[0] for p in pairs])
            corr = np.array([p[1] for p in pairs])
            return risk_controlled_threshold(
                conf, corr, risk.target_risk, risk.delta, risk.min_accepted
            )

        for model, pairs in by_model.items():
            self.policy.thresholds[model] = certify(pairs)
        if risk.conditional_on_routing:
            for model in by_model:
                # No routed calibration items -> nothing can be certified for initial answers.
                self.policy.initial_thresholds[model] = certify(routed.get(model, []))

    def route(self, query: Query, analysis: QueryAnalysis | None = None) -> str:
        """The model the router would choose initially (no generation)."""
        analysis = analysis or self.analyze(query)
        ctx = self.context(query)
        return self.router.route(
            query, analysis, self.difficulty.estimate(query, analysis, ctx), ctx
        ).model

    def _calibrate(self, model: str, language: str, raw: float) -> float | None:
        if self.calibration is None or not self.calibration_fitted:
            return None
        return self.calibration.predict(model, language, raw)

    # ---------------------------------------------------------------- inference
    def context(self, query: Query) -> CallContext:
        return CallContext(self.pool, query, self.seed)

    def analyze(self, query: Query) -> QueryAnalysis:
        return self.analyzer.analyze(query)

    def messages_for(
        self,
        query: Query,
        analysis: QueryAnalysis,
        strategy: str = "default",
        evidence: list[str] | None = None,
    ) -> list[Message]:
        return build_messages(query, analysis.category, strategy, evidence)

    def attempt(
        self,
        query: Query,
        analysis: QueryAnalysis,
        model: str,
        ctx: CallContext,
        stage: str = "initial",
        strategy: str = "default",
        evidence: list[str] | None = None,
        assess: bool = True,
    ) -> Attempt:
        """Generate one answer; ``assess=False`` skips confidence and verification."""
        messages = self.messages_for(query, analysis, strategy, evidence)
        metadata = {"strategy": strategy, **({"evidence": evidence} if evidence else {})}
        out = ctx.generate(model, messages, purpose=stage, metadata=metadata)
        answer = extract_answer(out.text, query.answer_type, query.choices)
        if not assess:
            return Attempt(
                stage,
                model,
                out.text,
                answer,
                info={"finish_reason": out.finish_reason, "latency_s": out.latency_s},
            )
        return self.finalize_attempt(
            query,
            analysis,
            model,
            out,
            answer,
            ctx,
            stage=stage,
            messages=messages,
            evidence=evidence,
        )

    def finalize_attempt(
        self,
        query: Query,
        analysis: QueryAnalysis,
        model: str,
        out: GenerationOutput,
        answer: str | None,
        ctx: CallContext,
        stage: str,
        confidence: ConfidenceResult | None = None,
        messages: list[Message] | None = None,
        evidence: list[str] | None = None,
    ) -> Attempt:
        if confidence is None and self.confidence is not None:
            inp = ConfidenceInput(
                query,
                model,
                messages or self.messages_for(query, analysis),
                out,
                answer,
                query.answer_type,
            )
            raw, details = self.confidence.score(inp, ctx)
            confidence = ConfidenceResult(
                raw, self.confidence.name, self._calibrate(model, analysis.language, raw), details
            )
        verification = None
        if self.verifier is not None:
            verification = self.verifier.verify(
                VerificationInput(query, model, out, answer, evidence), ctx
            )
        return Attempt(
            stage,
            model,
            out.text,
            answer,
            confidence,
            verification,
            info={"finish_reason": out.finish_reason, "latency_s": out.latency_s},
        )

    def profile(
        self,
        query: Query,
        analysis: QueryAnalysis | None = None,
        assess: bool = False,
    ) -> tuple[QueryAnalysis, dict[str, Attempt]]:
        """Initial attempt of *every* model (used to build training/calibration data and
        the oracle). Costs of profiling are not charged to any evaluated system."""
        analysis = analysis or self.analyze(query)
        ctx = self.context(query)
        return analysis, {
            m: self.attempt(query, analysis, m, ctx, assess=assess) for m in self.pool.names
        }

    def run(self, query: Query) -> PipelineResult:
        if self.router.requires_fit and not getattr(self.router, "fitted", True):
            raise RuntimeError(f"Router '{self.router.name}' must be fitted before run()")
        ctx = self.context(query)
        analysis = self.analyze(query)
        difficulty = self.difficulty.estimate(query, analysis, ctx)
        routing = self.router.route(query, analysis, difficulty, ctx)

        first = self.attempt(query, analysis, routing.model, ctx, stage="initial")
        first.trigger = self.policy.triggers(first, difficulty, initial=True)
        first.reliable = not first.trigger
        attempts = [first]
        initial_calls = len(ctx.calls)

        if self.config.escalation.enabled and not first.reliable:
            n_run = 0
            for stage in self.stages:
                if n_run >= self.config.escalation.max_stages:
                    break
                new = stage.run(self, query, analysis, attempts, ctx)
                if new is None:
                    continue
                n_run += 1
                new.trigger = self.policy.triggers(new, difficulty, initial=False)
                new.reliable = not new.trigger
                attempts.append(new)
                if new.reliable:
                    break

        final = self.policy.select_final(attempts) if len(attempts) > 1 else first
        return PipelineResult(
            query_id=query.id,
            query=query.text,
            analysis=analysis,
            difficulty=difficulty,
            routing=routing,
            attempts=attempts,
            calls=ctx.calls,
            final_index=attempts.index(final),
            escalation_causes=list(first.trigger),
            system=self.config.name,
            initial_call_count=initial_calls,
        )
