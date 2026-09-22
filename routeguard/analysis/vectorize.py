"""Query vectorisation for learned difficulty estimators and routers.

A query vector concatenates

* the hand-crafted features from :mod:`routeguard.analysis.features` (standardised),
* one-hot *detected* language and *predicted* category (never gold labels), and
* a text embedding.

Two embedders are provided. ``hashing`` (default) uses hashed character n-grams:
no download, script-agnostic, deterministic. ``sentence_transformer`` uses a
multilingual sentence encoder (optional ``embeddings`` extra).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np

from routeguard.analysis.features import FEATURE_NAMES
from routeguard.types import Query, QueryAnalysis
from routeguard.utils.imports import require


class Embedder(Protocol):
    name: str

    def embed(self, texts: Sequence[str]) -> np.ndarray: ...


class HashingEmbedder:
    name = "hashing"

    def __init__(self, n_features: int = 2048, ngram_range: tuple[int, int] = (2, 4)):
        from sklearn.feature_extraction.text import HashingVectorizer

        self.vectorizer = HashingVectorizer(
            analyzer="char_wb",
            ngram_range=ngram_range,
            n_features=n_features,
            alternate_sign=False,
            norm="l2",
        )

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(self.vectorizer.transform(list(texts)).toarray(), dtype=np.float32)


class SentenceTransformerEmbedder:
    name = "sentence_transformer"

    def __init__(
        self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    ):
        st = require("sentence_transformers", "embeddings", "The sentence-transformer embedder")
        self.model = st.SentenceTransformer(model_name)

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(
            self.model.encode(list(texts), normalize_embeddings=True), dtype=np.float32
        )


def build_embedder(kind: str = "hashing", **kwargs: object) -> Embedder:
    if kind == "hashing":
        return HashingEmbedder(**kwargs)  # type: ignore[arg-type]
    if kind == "sentence_transformer":
        return SentenceTransformerEmbedder(**kwargs)  # type: ignore[arg-type]
    raise ValueError(f"Unknown embedder '{kind}' (hashing|sentence_transformer)")


class QueryVectorizer:
    def __init__(self, embedder: Embedder | None = None, use_embedding: bool = True):
        self.embedder = embedder or HashingEmbedder()
        self.use_embedding = use_embedding
        self.languages: list[str] = []
        self.categories: list[str] = []
        self.mean: np.ndarray | None = None
        self.std: np.ndarray | None = None

    def _dense(self, analyses: Sequence[QueryAnalysis]) -> np.ndarray:
        return np.array(
            [[a.features[f] for f in FEATURE_NAMES] for a in analyses], dtype=np.float32
        )

    def fit(self, analyses: Sequence[QueryAnalysis]) -> QueryVectorizer:
        self.languages = sorted({a.language for a in analyses})
        self.categories = sorted({a.category for a in analyses})
        dense = self._dense(analyses)
        self.mean = dense.mean(axis=0)
        self.std = dense.std(axis=0) + 1e-6
        return self

    def transform(self, queries: Sequence[Query], analyses: Sequence[QueryAnalysis]) -> np.ndarray:
        if self.mean is None or self.std is None:
            raise RuntimeError("QueryVectorizer.transform called before fit")
        dense = (self._dense(analyses) - self.mean) / self.std
        lang = np.array(
            [[a.language == lang for lang in self.languages] for a in analyses], dtype=np.float32
        ).reshape(len(analyses), -1)
        cat = np.array(
            [[a.category == c for c in self.categories] for a in analyses], dtype=np.float32
        ).reshape(len(analyses), -1)
        blocks = [dense, lang, cat]
        if self.use_embedding:
            blocks.append(self.embedder.embed([q.text for q in queries]))
        return np.hstack(blocks)
