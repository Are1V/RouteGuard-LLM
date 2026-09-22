"""BM25 retrieval over a JSONL corpus (``{"id", "text", "language"?}`` per line).

BM25 (Robertson & Zaragoza, 2009) is used deliberately: it is transparent,
deterministic, needs no embedding model, and its behaviour across languages is
easy to analyse (e.g. Kazakh agglutinative morphology lowers exact-token overlap,
which shows up directly as lower retrieval recall). Token normalisation folds
Arabic/Persian letter variants and digits (see ``routeguard.utils.text``).
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from routeguard.utils.text import tokenize


@dataclass
class Document:
    id: str
    text: str
    language: str | None = None


@dataclass
class Hit:
    doc: Document
    score: float
    rank: int


class BM25Retriever:
    def __init__(
        self,
        documents: list[Document],
        k1: float = 1.5,
        b: float = 0.75,
        prefix_len: int | None = None,
    ):
        """``prefix_len`` optionally truncates tokens to a prefix (a crude stemmer that
        helps morphologically rich languages; ``None`` disables it)."""
        if not documents:
            raise ValueError("BM25Retriever needs a non-empty corpus")
        self.documents = documents
        self.k1, self.b, self.prefix_len = k1, b, prefix_len
        self.doc_tokens = [Counter(self._tok(d.text)) for d in documents]
        self.doc_len = [sum(c.values()) for c in self.doc_tokens]
        self.avg_len = sum(self.doc_len) / len(documents)
        df: Counter[str] = Counter()
        for counts in self.doc_tokens:
            df.update(counts.keys())
        n = len(documents)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def _tok(self, text: str) -> list[str]:
        toks = tokenize(text)
        return [t[: self.prefix_len] for t in toks] if self.prefix_len else toks

    @classmethod
    def from_jsonl(cls, path: str | Path, **kwargs: float | int | None) -> BM25Retriever:
        docs = []
        with Path(path).open(encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if "id" not in row or "text" not in row:
                    raise ValueError(f"{path}:{line_no}: corpus rows need 'id' and 'text'")
                docs.append(Document(str(row["id"]), row["text"], row.get("language")))
        return cls(docs, **kwargs)  # type: ignore[arg-type]

    def search(self, query: str, k: int = 3, language: str | None = None) -> list[Hit]:
        q_terms = [t for t in set(self._tok(query)) if t in self.idf]
        scores = []
        for i, counts in enumerate(self.doc_tokens):
            if language and self.documents[i].language and self.documents[i].language != language:
                continue
            s = 0.0
            norm = self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avg_len)
            for t in q_terms:
                tf = counts.get(t, 0)
                if tf:
                    s += self.idf[t] * tf * (self.k1 + 1) / (tf + norm)
            if s > 0:
                scores.append((s, i))
        scores.sort(key=lambda x: (-x[0], x[1]))
        return [Hit(self.documents[i], s, r + 1) for r, (s, i) in enumerate(scores[:k])]
