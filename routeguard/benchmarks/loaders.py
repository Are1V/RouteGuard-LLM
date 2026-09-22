"""Dataset loaders.

``jsonl`` reads items in the RouteGuard schema and needs no extra dependency.
All other loaders convert a public Hugging Face dataset (``datasets`` extra) at a
**pinned revision**. Nothing is downloaded unless an experiment config (or
``routeguard prepare-data``) asks for it.

``limit`` is applied *per language* after a deterministic, seed-independent
ordering by a hash of the item id, so every seed and every system evaluates the
same item pool and only the train/calibration/test partition changes.

Licenses were taken from the Hugging Face dataset cards (see docs/benchmarks.md).
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from routeguard.benchmarks.schema import Item
from routeguard.config import DatasetConfig
from routeguard.types import AnswerType
from routeguard.utils.imports import require
from routeguard.utils.seeding import stable_hash

LETTERS = "ABCDEFGHIJ"


@dataclass(frozen=True)
class HubSource:
    repo: str
    revision: str
    license: str


SOURCES: dict[str, HubSource] = {
    "gsm8k": HubSource("openai/gsm8k", "740312add88f781978c0658806c59bc2815b9866", "MIT"),
    "mgsm": HubSource("juletxara/mgsm", "b2f13d426afe3be8d69a7e739b36724db8b66bbc", "CC-BY-SA-4.0"),
    "belebele": HubSource(
        "facebook/belebele", "7899cdfa4e1e0d733fd77c848e2c273cb1d32be2", "CC-BY-SA-4.0"
    ),
    "global_mmlu": HubSource(
        "CohereLabs/Global-MMLU", "0e619dbeb34206cd48705a1a0ea7fb21cae09993", "Apache-2.0"
    ),
    "sib200": HubSource(
        "Davlan/sib200", "38977a667f6fc264d5c26ec57a01e16db040b358", "CC-BY-SA-4.0"
    ),
    "mbpp": HubSource(
        "google-research-datasets/mbpp", "4bb6404fdc6cacfda99d4ac4205087b89d32030c", "CC-BY-4.0"
    ),
    "nq_open": HubSource(
        "google-research-datasets/nq_open",
        "5dd9790a83002ad084ddeb7c420dc716852c6f28",
        "CC-BY-SA-3.0",
    ),
    "arc": HubSource("allenai/ai2_arc", "210d026faf9955653af8916fad021475a3f00453", "CC-BY-SA-4.0"),
}

# FLORES-style codes used by Belebele / SIB-200 -> (ISO 639-1, variant label)
FLORES_LANG = {
    "eng_Latn": ("en", None),
    "kaz_Cyrl": ("kk", None),
    "rus_Cyrl": ("ru", None),
    "pes_Arab": ("fa", "pes_Arab"),
    "prs_Arab": ("fa", "prs_Arab"),
    "arb_Arab": ("ar", None),
}


def _hub(name: str, config: str | None, split: str, revision: str | None = None) -> Iterable[dict]:
    datasets = require("datasets", "data", f"The '{name}' loader")
    src = SOURCES[name]
    return datasets.load_dataset(src.repo, config, split=split, revision=revision or src.revision)


def _take(items: list[Item], limit: int | None) -> list[Item]:
    """Deterministic per-language subsample (independent of the experiment seed)."""
    if limit is None:
        return items
    by_lang: dict[str, list[Item]] = {}
    for it in items:
        by_lang.setdefault(it.language_variant or it.language, []).append(it)
    out: list[Item] = []
    for group in by_lang.values():
        # Order by the *parallel* id when present so every language keeps the same items.
        group.sort(key=lambda it: stable_hash("subsample", it.parallel_id or it.id))
        out.extend(group[:limit])
    return out


# ------------------------------------------------------------------------ loaders
def load_jsonl(cfg: DatasetConfig) -> list[Item]:
    if not cfg.path:
        raise ValueError("jsonl loader needs 'path'")
    path = Path(cfg.path)
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset file not found: {path} (paths are relative to the "
            "working directory; run from the repository root)"
        )
    items = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                items.append(Item.model_validate(json.loads(line)))
            except Exception as exc:
                raise ValueError(f"{path}:{line_no}: invalid item: {exc}") from exc
    languages = cfg.options.get("languages")
    if languages:
        items = [it for it in items if it.language in languages]
    return _take(items, cfg.limit)


def load_gsm8k(cfg: DatasetConfig) -> list[Item]:
    items = []
    for i, row in enumerate(
        _hub("gsm8k", "main", cfg.options.get("split", "test"), cfg.options.get("revision"))
    ):
        answer = row["answer"].split("####")[-1].strip().replace(",", "")
        items.append(
            Item(
                id=f"gsm8k-{i}",
                question=row["question"],
                answer=answer,
                answer_type=AnswerType.NUMERIC,
                category="math",
                language="en",
                source="gsm8k",
                license=SOURCES["gsm8k"].license,
            )
        )
    return _take(items, cfg.limit)


def load_mgsm(cfg: DatasetConfig) -> list[Item]:
    items = []
    for lang in cfg.options.get("languages", ["en", "ru"]):
        rows = _hub("mgsm", lang, cfg.options.get("split", "test"), cfg.options.get("revision"))
        for i, row in enumerate(rows):
            items.append(
                Item(
                    id=f"mgsm-{lang}-{i}",
                    question=row["question"],
                    answer=str(row["answer_number"]),
                    answer_type=AnswerType.NUMERIC,
                    category="math",
                    language=lang,
                    parallel_id=f"mgsm-{i}",
                    source="mgsm",
                    license=SOURCES["mgsm"].license,
                )
            )
    return _take(items, cfg.limit)


def load_belebele(cfg: DatasetConfig) -> list[Item]:
    items = []
    for code in cfg.options.get("languages", ["eng_Latn", "kaz_Cyrl", "rus_Cyrl", "pes_Arab"]):
        lang, variant = FLORES_LANG.get(code, (code.split("_")[0], code))
        for row in _hub("belebele", code, "test", cfg.options.get("revision")):
            pid = f"belebele-{stable_hash(row['link'], row['question_number'], length=10)}"
            items.append(
                Item(
                    id=f"{pid}-{code}",
                    question=row["question"].strip(),
                    answer=LETTERS[int(row["correct_answer_num"]) - 1],
                    answer_type=AnswerType.CHOICE,
                    choices=[row[f"mc_answer{k}"] for k in range(1, 5)],
                    context=row["flores_passage"],
                    category="reading_comprehension",
                    language=lang,
                    language_variant=variant,
                    parallel_id=pid,
                    source="belebele",
                    license=SOURCES["belebele"].license,
                )
            )
    return _take(items, cfg.limit)


def load_global_mmlu(cfg: DatasetConfig) -> list[Item]:
    items = []
    subjects = set(cfg.options.get("subjects", []))
    for lang in cfg.options.get("languages", ["en", "ru", "fa"]):
        for row in _hub(
            "global_mmlu", lang, cfg.options.get("split", "test"), cfg.options.get("revision")
        ):
            if subjects and row["subject"] not in subjects:
                continue
            items.append(
                Item(
                    id=f"gmmlu-{lang}-{row['sample_id']}",
                    question=row["question"],
                    answer=row["answer"],
                    answer_type=AnswerType.CHOICE,
                    choices=[row[f"option_{k}"] for k in "abcd"],
                    category="science" if row["subject_category"] == "STEM" else "factual_qa",
                    language=lang,
                    parallel_id=f"gmmlu-{row['sample_id']}",
                    source="global_mmlu",
                    license=SOURCES["global_mmlu"].license,
                    metadata={
                        "subject": row["subject"],
                        "cultural_sensitivity": row["cultural_sensitivity_label"],
                    },
                )
            )
    return _take(items, cfg.limit)


SIB_TOPICS = [
    "science/technology",
    "travel",
    "politics",
    "sports",
    "health",
    "entertainment",
    "geography",
]


def load_sib200(cfg: DatasetConfig) -> list[Item]:
    items = []
    for code in cfg.options.get(
        "languages", ["eng_Latn", "kaz_Cyrl", "rus_Cyrl", "pes_Arab", "prs_Arab"]
    ):
        lang, variant = FLORES_LANG.get(code, (code.split("_")[0], code))
        for row in _hub(
            "sib200", code, cfg.options.get("split", "test"), cfg.options.get("revision")
        ):
            pid = f"sib200-{row['index_id']}"
            items.append(
                Item(
                    id=f"{pid}-{code}",
                    question="Which topic does the passage belong to?",
                    context=row["text"],
                    answer=LETTERS[SIB_TOPICS.index(row["category"])],
                    answer_type=AnswerType.CHOICE,
                    choices=list(SIB_TOPICS),
                    category="classification",
                    language=lang,
                    language_variant=variant,
                    parallel_id=pid,
                    source="sib200",
                    license=SOURCES["sib200"].license,
                )
            )
    return _take(items, cfg.limit)


def load_mbpp(cfg: DatasetConfig) -> list[Item]:
    items = []
    for row in _hub(
        "mbpp", "sanitized", cfg.options.get("split", "test"), cfg.options.get("revision")
    ):
        tests = list(row["test_list"])
        m = re.search(r"assert\s+(?:not\s+)?\(?\s*(?:set\()?\s*(\w+)\s*\(", tests[0])
        entry = m.group(1) if m else None
        imports = list(row.get("test_imports") or [])
        question = f"{row['prompt'].strip()}\nYour code should pass these tests:\n" + "\n".join(
            tests
        )
        items.append(
            Item(
                id=f"mbpp-{row['task_id']}",
                question=question,
                answer=row["code"],
                answer_type=AnswerType.CODE,
                category="coding",
                language="en",
                public_tests=imports + tests,
                eval_tests=imports + tests,
                entry_point=entry,
                solution=row["code"],
                source="mbpp",
                license=SOURCES["mbpp"].license,
            )
        )
    return _take(items, cfg.limit)


def load_nq_open(cfg: DatasetConfig) -> list[Item]:
    items = []
    for i, row in enumerate(
        _hub("nq_open", None, cfg.options.get("split", "validation"), cfg.options.get("revision"))
    ):
        answers = row["answer"]
        if isinstance(answers, str):
            answers = ast.literal_eval(answers)
        items.append(
            Item(
                id=f"nq-{i}",
                question=row["question"].strip() + "?",
                answer=[str(a) for a in answers],
                answer_type=AnswerType.TEXT,
                category="factual_qa",
                language="en",
                source="nq_open",
                license=SOURCES["nq_open"].license,
            )
        )
    return _take(items, cfg.limit)


def load_arc(cfg: DatasetConfig) -> list[Item]:
    items = []
    subset = cfg.options.get("subset", "ARC-Challenge")
    for row in _hub("arc", subset, cfg.options.get("split", "test"), cfg.options.get("revision")):
        labels = list(row["choices"]["label"])
        if row["answerKey"] not in labels:
            continue
        items.append(
            Item(
                id=f"arc-{row['id']}",
                question=row["question"],
                answer=LETTERS[labels.index(row["answerKey"])],
                answer_type=AnswerType.CHOICE,
                choices=list(row["choices"]["text"]),
                category="science",
                language="en",
                source=f"arc-{subset.split('-')[-1].lower()}",
                license=SOURCES["arc"].license,
            )
        )
    return _take(items, cfg.limit)


LOADERS: dict[str, Callable[[DatasetConfig], list[Item]]] = {
    "jsonl": load_jsonl,
    "gsm8k": load_gsm8k,
    "mgsm": load_mgsm,
    "belebele": load_belebele,
    "global_mmlu": load_global_mmlu,
    "sib200": load_sib200,
    "mbpp": load_mbpp,
    "nq_open": load_nq_open,
    "arc": load_arc,
}


def register_loader(name: str, fn: Callable[[DatasetConfig], list[Item]]) -> None:
    LOADERS[name] = fn


def load_dataset(cfg: DatasetConfig) -> list[Item]:
    if cfg.loader not in LOADERS:
        raise ValueError(f"Unknown loader '{cfg.loader}'. Available: {sorted(LOADERS)}")
    items = LOADERS[cfg.loader](cfg)
    if not items:
        raise ValueError(f"Loader '{cfg.loader}' returned no items for {cfg.model_dump()}")
    return items


def load_all(configs: list[DatasetConfig]) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    for cfg in configs:
        for it in load_dataset(cfg):
            if it.id in seen:
                raise ValueError(f"Duplicate item id '{it.id}' across datasets")
            seen.add(it.id)
            items.append(it)
    return items


def write_jsonl(items: list[Item], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(
                json.dumps(it.model_dump(mode="json", exclude_none=True), ensure_ascii=False) + "\n"
            )


def dataset_fingerprint(items: list[Item]) -> str:
    return stable_hash(
        *sorted(
            json.dumps(i.model_dump(mode="json"), sort_keys=True, ensure_ascii=False) for i in items
        ),
        length=16,
    )


def describe(items: list[Item]) -> dict[str, Any]:
    from collections import Counter

    return {
        "n_items": len(items),
        "by_source": dict(Counter(i.source for i in items)),
        "by_language": dict(Counter(i.language_variant or i.language for i in items)),
        "by_category": dict(Counter(i.category for i in items)),
    }
