import json

import pytest
from pydantic import ValidationError

from routeguard.benchmarks import Item, load_dataset, loaders, make_splits
from routeguard.benchmarks.loaders import dataset_fingerprint, describe, write_jsonl
from routeguard.config import DatasetConfig, SplitConfig
from routeguard.types import AnswerType
from tests.conftest import ROOT

SMOKE = str(ROOT / "benchmarks" / "samples" / "smoke.jsonl")


def test_smoke_fixture_loads_and_covers_four_languages():
    items = load_dataset(DatasetConfig(loader="jsonl", path=SMOKE))
    info = describe(items)
    assert set(info["by_language"]) == {"en", "kk", "ru", "fa"}
    assert {"math", "factual_qa", "coding"} <= set(info["by_category"])


def test_item_validation():
    with pytest.raises(ValidationError, match="letters"):
        Item(
            id="x",
            question="q",
            answer="E",
            answer_type=AnswerType.CHOICE,
            category="c",
            language="en",
            choices=["a", "b"],
        )
    with pytest.raises(ValidationError, match="eval_tests"):
        Item(
            id="x",
            question="q",
            answer="s",
            answer_type=AnswerType.CODE,
            category="c",
            language="en",
        )
    with pytest.raises(ValidationError):
        Item.model_validate(
            {
                "id": "x",
                "question": "q",
                "answer": "1",
                "answer_type": "numeric",
                "category": "math",
                "unknown_field": 1,
            }
        )


def test_query_conversion_keeps_gold_out_of_visible_fields():
    it = Item(
        id="x",
        question="q",
        answer="1",
        answer_type=AnswerType.NUMERIC,
        category="math",
        language="kk",
    )
    q = it.to_query()
    assert q.reference["answer"] == "1" and q.text == "q" and q.language == "kk"


def test_jsonl_errors_point_to_line(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"id": "a", "question": "q", "answer": "1", "answer_type": "numeric", '
        '"category": "m", "language": "en"}\n{"id": "b"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"bad\.jsonl:2"):
        load_dataset(DatasetConfig(loader="jsonl", path=str(bad)))
    with pytest.raises(FileNotFoundError):
        load_dataset(DatasetConfig(loader="jsonl", path=str(tmp_path / "missing.jsonl")))


def test_limit_is_per_language_and_keeps_parallel_items_aligned():
    items = load_dataset(DatasetConfig(loader="jsonl", path=SMOKE, limit=3))
    by_lang = {}
    for it in items:
        by_lang.setdefault(it.language, set()).add(it.parallel_id)
    assert all(len(v) <= 3 for v in by_lang.values())
    assert by_lang["ru"] == by_lang["kk"] == by_lang["fa"]


def test_splits_are_group_aware_deterministic_and_seed_dependent():
    items = load_dataset(DatasetConfig(loader="jsonl", path=SMOKE))
    cfg = SplitConfig(train=0.5, calibration=0.2, test=0.3)
    s0, s0b, s1 = make_splits(items, cfg, 0), make_splits(items, cfg, 0), make_splits(items, cfg, 1)
    assert [i.id for i in s0.test] == [i.id for i in s0b.test]
    assert [i.id for i in s0.test] != [i.id for i in s1.test]
    assert len(s0.train) + len(s0.calibration) + len(s0.test) == len(items)
    groups = [{i.parallel_id or i.id for i in part} for part in (s0.train, s0.calibration, s0.test)]
    assert not (groups[0] & groups[2]) and not (groups[1] & groups[2])


def test_write_and_fingerprint(tmp_path):
    items = load_dataset(DatasetConfig(loader="jsonl", path=SMOKE, limit=2))
    write_jsonl(items, tmp_path / "x.jsonl")
    again = load_dataset(DatasetConfig(loader="jsonl", path=str(tmp_path / "x.jsonl")))
    assert dataset_fingerprint(items) == dataset_fingerprint(again)


def _fake_hub(rows):
    def fake(name, config, split, revision=None):
        return rows[(name, config)]

    return fake


def test_hub_loaders_convert_rows(monkeypatch):
    rows = {
        ("gsm8k", "main"): [{"question": "2+2?", "answer": "reasoning\n#### 1,004"}],
        ("belebele", "kaz_Cyrl"): [
            {
                "link": "l",
                "question_number": 1,
                "flores_passage": "p",
                "question": " Q ",
                "mc_answer1": "a",
                "mc_answer2": "b",
                "mc_answer3": "c",
                "mc_answer4": "d",
                "correct_answer_num": "2",
            }
        ],
        ("sib200", "prs_Arab"): [{"index_id": 7, "category": "sports", "text": "متن"}],
        ("mbpp", "sanitized"): [
            {
                "task_id": 11,
                "prompt": "Write f.",
                "code": "def f(x): return x",
                "test_list": ["assert f(1) == 1"],
                "test_imports": [],
            }
        ],
        ("nq_open", None): [{"question": "who", "answer": ["A", "B"]}],
        ("mgsm", "ru"): [{"question": "сколько?", "answer_number": 5}],
        ("global_mmlu", "fa"): [
            {
                "sample_id": "s/1",
                "subject": "physics",
                "subject_category": "STEM",
                "question": "q",
                "option_a": "1",
                "option_b": "2",
                "option_c": "3",
                "option_d": "4",
                "answer": "C",
                "cultural_sensitivity_label": "CA",
            }
        ],
        ("arc", "ARC-Challenge"): [
            {
                "id": "a1",
                "question": "q",
                "answerKey": "3",
                "choices": {"label": ["1", "2", "3"], "text": ["x", "y", "z"]},
            }
        ],
    }
    monkeypatch.setattr(loaders, "_hub", _fake_hub(rows))
    g = load_dataset(DatasetConfig(loader="gsm8k"))[0]
    assert g.answer == "1004" and g.answer_type == AnswerType.NUMERIC
    b = load_dataset(DatasetConfig(loader="belebele", options={"languages": ["kaz_Cyrl"]}))[0]
    assert (b.answer, b.language, b.context) == ("B", "kk", "p")
    s = load_dataset(DatasetConfig(loader="sib200", options={"languages": ["prs_Arab"]}))[0]
    assert (s.language, s.language_variant, s.answer) == ("fa", "prs_Arab", "D")
    m = load_dataset(DatasetConfig(loader="mbpp"))[0]
    assert m.entry_point == "f" and m.eval_tests == ["assert f(1) == 1"]
    assert load_dataset(DatasetConfig(loader="nq_open"))[0].answer == ["A", "B"]
    assert (
        load_dataset(DatasetConfig(loader="mgsm", options={"languages": ["ru"]}))[0].answer == "5"
    )
    gm = load_dataset(DatasetConfig(loader="global_mmlu", options={"languages": ["fa"]}))[0]
    assert gm.category == "science" and gm.metadata["cultural_sensitivity"] == "CA"
    assert load_dataset(DatasetConfig(loader="arc"))[0].answer == "C"
    with pytest.raises(ValueError):
        load_dataset(DatasetConfig(loader="nope"))


def test_curated_template_is_valid():
    path = ROOT / "benchmarks" / "samples" / "curated_template.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert rows
    for r in rows:
        Item.model_validate(r)
