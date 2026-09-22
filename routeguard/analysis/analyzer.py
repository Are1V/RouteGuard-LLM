"""Query analyzer: language detection + task classification + feature extraction."""

from __future__ import annotations

from routeguard.analysis.features import extract_features
from routeguard.analysis.language import LanguageDetector
from routeguard.analysis.task import TaskClassifier
from routeguard.types import Query, QueryAnalysis


class QueryAnalyzer:
    def __init__(self, language_detector: LanguageDetector, task_classifier: TaskClassifier):
        self.language_detector = language_detector
        self.task_classifier = task_classifier

    def analyze(self, query: Query) -> QueryAnalysis:
        # The language of a query is the language of everything the model must read:
        # e.g. an English instruction over a Dari passage is a Dari query.
        text = query.text if not query.context else f"{query.text}\n{query.context[:1000]}"
        detection = self.language_detector.detect(text)
        language_override = query.metadata.get("language_override")
        if isinstance(language_override, str) and language_override:
            detection.language = language_override
            detection.confidence = 1.0
        category, cat_conf = self.task_classifier.classify(query)
        non_latin = 1.0 - detection.scripts.get("Latin", 0.0) if detection.scripts else 0.0
        return QueryAnalysis(
            language=detection.language,
            language_confidence=detection.confidence,
            scripts=detection.scripts,
            category=category,
            category_confidence=cat_conf,
            features=extract_features(query, non_latin_ratio=non_latin),
        )
