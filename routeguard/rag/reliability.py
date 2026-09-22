"""RAG reliability evaluation.

The goal is not "build a RAG system" but to *attribute* RAG failures:

* **retrieval failure** – no relevant passage in the top-k (by gold passage id when
  annotated, otherwise gold answer string match);
* **generation failure** – relevant evidence was retrieved but the answer is wrong;
* **answer without evidence** – retrieval failed but the model answered anyway
  (instead of abstaining); these answers are correct only by luck or parametric
  knowledge and are reported separately;
* **groundedness** – share of answer content tokens supported by the evidence;
* **citation support** – when the answer cites ``[n]``, whether passage ``n`` supports it;
* **unsupported answer** – answer tokens largely absent from evidence and question.

Everything is computed deterministically from retrieved text, gold answers, and
gold passage ids, so it is language-agnostic and reproducible. Lexical support
is a proxy for entailment and is documented as such (see docs/benchmarks.md).
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from routeguard.benchmarks.schema import Item
from routeguard.config import ScoringConfig
from routeguard.evaluation.records import score_item
from routeguard.rag.retriever import BM25Retriever, Document, Hit
from routeguard.utils.seeding import stable_hash
from routeguard.utils.text import normalize_text, tokenize

ABSTAIN_PATTERNS = re.compile(
    r"not (in|contained in|mentioned in|present in) the (evidence|passages?|context)|"
    r"cannot be (determined|answered)|insufficient (evidence|information)|no answer|unknown",
    re.IGNORECASE,
)
_CITATION = re.compile(r"\[(\d+)\]")


def build_passage_corpus(items: Sequence[Item]) -> tuple[list[Document], list[Item]]:
    """Turn reading-comprehension items into an open-book retrieval task.

    Unique passages become the corpus (one per language); each item loses its
    passage, which is kept only as evaluation metadata (``gold_doc_ids``).
    """
    docs: dict[str, Document] = {}
    converted = []
    for it in items:
        if not it.context:
            raise ValueError(f"{it.id}: RAG evaluation needs items with a passage (context)")
        digest = stable_hash(normalize_text(it.context), length=12)
        doc_id = f"{it.language_variant or it.language}:{digest}"
        docs.setdefault(doc_id, Document(doc_id, it.context, it.language))
        meta = {**it.metadata, "gold_doc_ids": [doc_id], "gold_passage": it.context}
        converted.append(it.model_copy(update={"context": None, "metadata": meta}))
    return list(docs.values()), converted


@dataclass
class RagOutcome:
    item_id: str
    language: str
    retrieval_hit: bool
    reciprocal_rank: float
    groundedness: float
    citation_supported: bool | None
    abstained: bool
    correct: bool
    attribution: str


def _support(answer: str, texts: Sequence[str]) -> float:
    toks = set(tokenize(answer))
    if not toks:
        return 0.0
    pool = set(tokenize(" ".join(texts)))
    return len(toks & pool) / len(toks)


def evaluate_item(
    item: Item, hits: Sequence[Hit], response: str, answer: str | None, scoring: ScoringConfig
) -> RagOutcome:
    gold_ids = item.metadata.get("gold_doc_ids") or []
    ranks = [h.rank for h in hits if h.doc.id in gold_ids]
    if gold_ids:
        hit = bool(ranks)
    else:
        golds = item.answer if isinstance(item.answer, list) else [item.answer]
        hit = any(normalize_text(str(g)) in normalize_text(h.doc.text) for g in golds for h in hits)
    rr = 1.0 / min(ranks) if ranks else 0.0
    texts = [h.doc.text for h in hits]
    answer_text = answer or ""
    letters = "ABCDEFGHIJ"
    if item.answer_type.value == "choice" and item.choices and answer and answer in letters:
        index = letters.index(answer)
        answer_text = item.choices[index] if index < len(item.choices) else ""
    grounded = _support(answer_text, texts)
    cited = [int(c) for c in _CITATION.findall(response)]
    citation_ok: bool | None = None
    if cited:
        valid = [texts[c - 1] for c in cited if 1 <= c <= len(texts)]
        citation_ok = bool(valid) and _support(answer_text, valid) >= 0.5
    abstained = bool(ABSTAIN_PATTERNS.search(answer or response[-300:]))
    correct = score_item(answer, item, scoring).correct
    if correct:
        attribution = "correct" if hit else "correct_without_evidence"
    elif abstained:
        attribution = "abstained_retrieval_failure" if not hit else "abstained_despite_evidence"
    else:
        attribution = "generation_failure" if hit else "retrieval_failure"
    return RagOutcome(
        item.id,
        item.language_variant or item.language,
        hit,
        rr,
        grounded,
        citation_ok,
        abstained,
        correct,
        attribution,
    )


def summarize(outcomes: Sequence[RagOutcome]) -> dict[str, Any]:
    def agg(rows: Sequence[RagOutcome]) -> dict[str, float]:
        n = len(rows)
        miss = [r for r in rows if not r.retrieval_hit]
        hitr = [r for r in rows if r.retrieval_hit]
        cites = [r.citation_supported for r in rows if r.citation_supported is not None]
        return {
            "n": float(n),
            "accuracy": float(np.mean([r.correct for r in rows])) if n else float("nan"),
            "retrieval_recall_at_k": float(np.mean([r.retrieval_hit for r in rows]))
            if n
            else float("nan"),
            "mrr": float(np.mean([r.reciprocal_rank for r in rows])) if n else float("nan"),
            "groundedness_mean": float(np.mean([r.groundedness for r in rows]))
            if n
            else float("nan"),
            "accuracy_given_hit": float(np.mean([r.correct for r in hitr]))
            if hitr
            else float("nan"),
            "accuracy_given_miss": float(np.mean([r.correct for r in miss]))
            if miss
            else float("nan"),
            "answer_without_evidence_rate": (
                float(np.mean([not r.abstained for r in miss])) if miss else float("nan")
            ),
            "abstention_rate": float(np.mean([r.abstained for r in rows])) if n else float("nan"),
            "citation_support_rate": float(np.mean(cites)) if cites else float("nan"),
            "retrieval_failure_share": float(
                np.mean([r.attribution == "retrieval_failure" for r in rows])
            )
            if n
            else float("nan"),
            "generation_failure_share": float(
                np.mean([r.attribution == "generation_failure" for r in rows])
            )
            if n
            else float("nan"),
        }

    by_lang: dict[str, list[RagOutcome]] = defaultdict(list)
    for o in outcomes:
        by_lang[o.language].append(o)
    return {
        "overall": agg(outcomes),
        "by_language": {k: agg(v) for k, v in sorted(by_lang.items())},
    }


__all__ = ["BM25Retriever", "RagOutcome", "build_passage_corpus", "evaluate_item", "summarize"]
