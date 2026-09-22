import json

import pytest

from routeguard.benchmarks import Item
from routeguard.config import ScoringConfig
from routeguard.context import CallContext
from routeguard.rag.reliability import build_passage_corpus, evaluate_item, summarize
from routeguard.rag.retriever import BM25Retriever, Document
from routeguard.tools.agent import ToolAgent
from routeguard.tools.base import (
    BUILTIN_TOOLS,
    ToolCall,
    ToolError,
    ToolTrace,
    calculator,
    parse_tool_call,
    safe_eval,
    unit_convert,
)
from routeguard.tools.evaluation import ToolCase, label_trace, summarize_tool_eval
from routeguard.tracking.run import JsonlWriter, RunDirectory, environment, git_state
from routeguard.types import AnswerType


def test_safe_eval_and_tools():
    assert calculator("(2 + 3) * 4 ^ 2") == "80"
    assert calculator("7 / 2") == "3.5"
    for bad in ("__import__('os')", "a + 1", "2 ** 1000", "1/0"):
        with pytest.raises(ToolError):
            safe_eval(bad)
    assert unit_convert(212, "f", "c") == "100"
    assert unit_convert(3, "mi", "m") == "4828.032"
    assert unit_convert(3, "miles", "metres") == "4828.032"  # full names accepted
    assert "Supported units" in BUILTIN_TOOLS["unit_convert"].signature()
    with pytest.raises(ToolError):
        unit_convert(1, "kg", "m")
    with pytest.raises(ToolError):
        BUILTIN_TOOLS["calculator"].run({"expr": "1"})


def test_parse_tool_call():
    call = parse_tool_call(
        'I will compute.\nTOOL_CALL: {"name": "calculator", '
        '"arguments": {"expression": "2+2"}} then wait'
    )
    assert call.name == "calculator" and call.arguments == {"expression": "2+2"}
    assert parse_tool_call("no call here") is None
    assert parse_tool_call("TOOL_CALL: {not json}").malformed


def _case(**kw):
    base = {
        "id": "c",
        "question": "What is 12*12?",
        "answer": "144",
        "required_tools": ["calculator"],
    }
    return ToolCase(**{**base, **kw})


def test_tool_failure_labels():
    ok = ToolTrace(
        [ToolCall("calculator", {"expression": "12*12"}, "", result="144")],
        ["TOOL_CALL...", "Final answer: 144"],
        "Final answer: 144",
    )
    assert label_trace(_case(), ok)["labels"] == [] and label_trace(_case(), ok)["correct"]
    missing = ToolTrace([], ["Final answer: 140"], "Final answer: 140")
    assert "missing_required_call" in label_trace(_case(), missing)["labels"]
    fabricated = ToolTrace(
        [],
        ["The calculator returned 144.\nFinal answer: 144"],
        "The calculator returned 144.\nFinal answer: 144",
    )
    assert "fabricated_result" in label_trace(_case(), fabricated)["labels"]
    contradicted = ToolTrace(
        [ToolCall("calculator", {}, "", result="144")],
        ["x", "Final answer: 145"],
        "Final answer: 145",
    )
    assert "contradicted_result" in label_trace(_case(), contradicted)["labels"]
    ignored = ToolTrace(
        [ToolCall("calculator", {}, "", result="144")], ["x", "I am not sure."], "I am not sure."
    )
    assert "ignored_result" in label_trace(_case(), ignored)["labels"]
    unnecessary = ToolTrace(
        [ToolCall("calculator", {}, "", result="4")], ["x", "Final answer: 4"], "Final answer: 4"
    )
    labels = label_trace(_case(required_tools=[], answer="4"), unnecessary)["labels"]
    assert labels == ["unnecessary_call"]
    wrong = ToolTrace([ToolCall("unit_convert", {}, "", error="bad")], ["x", "Final answer: 1"], "")
    assert {"wrong_tool", "malformed_arguments"} <= set(label_trace(_case(), wrong)["labels"])
    summary = summarize_tool_eval([label_trace(_case(), ok), label_trace(_case(), missing)])
    assert summary["accuracy"] == 0.5 and summary["failure_rates"]["missing_required_call"] == 0.5


def test_tool_agent_loop_with_simulator(sim_pool):
    case = _case(expected_calls=[{"name": "calculator", "arguments": {"expression": "12*12"}}])
    q = case.to_query()
    trace = ToolAgent(list(BUILTIN_TOOLS.values())).run(q, "large", CallContext(sim_pool, q))
    assert trace.final_text and trace.last_output is not None
    assert all(c.purpose == "tool_agent" for c in CallContext(sim_pool, q).calls)


def test_bm25_multilingual_retrieval():
    docs = [
        Document("fa", "ارتفاع کوه دماوند ۵۶۰۹ متر است", "fa"),
        Document("en", "Mount Damavand is the highest peak in Iran", "en"),
        Document("kk", "Бәйтерек монументінің биіктігі 97 метр", "kk"),
    ]
    r = BM25Retriever(docs)
    assert r.search("ارتفاع دماوند چند متر است؟", k=1)[0].doc.id == "fa"
    assert r.search("5609", k=1)[0].doc.id == "fa"  # Persian digits are normalised
    assert r.search("Damavand", k=3, language="kk") == []
    with pytest.raises(ValueError):
        BM25Retriever([])


def test_rag_attribution():
    items = [
        Item(
            id=f"i{i}",
            question=f"q{i}",
            answer="7",
            answer_type=AnswerType.NUMERIC,
            category="retrieval",
            language="en",
            context=f"passage {i} says seven 7",
        )
        for i in range(2)
    ]
    docs, rag_items = build_passage_corpus(items)
    assert len(docs) == 2 and all(it.context is None for it in rag_items)
    r = BM25Retriever(docs)
    hits_right = [
        h
        for h in r.search("passage 0", k=2)
        if h.doc.id == rag_items[0].metadata["gold_doc_ids"][0]
    ]
    ok = evaluate_item(rag_items[0], hits_right, "Final answer: 7", "7", ScoringConfig())
    assert ok.retrieval_hit and ok.correct and ok.attribution == "correct"
    wrong_hits = [h for h in r.search("passage 1", k=1)]
    gen_fail = evaluate_item(rag_items[1], wrong_hits, "Final answer: 8", "8", ScoringConfig())
    assert gen_fail.attribution == "generation_failure"
    ret_fail = evaluate_item(rag_items[0], wrong_hits, "Final answer: 9", "9", ScoringConfig())
    assert ret_fail.attribution == "retrieval_failure"
    summary = summarize([ok, gen_fail, ret_fail])
    assert summary["overall"]["accuracy"] == pytest.approx(1 / 3)
    assert summary["overall"]["answer_without_evidence_rate"] == 1.0


def test_tracking(tmp_path):
    rd = RunDirectory(tmp_path, "exp")
    rd2 = RunDirectory(tmp_path, "exp")
    assert rd.path != rd2.path and (rd.path / "raw").is_dir()
    rd.write_json("processed/x.json", {"a": 1})
    with JsonlWriter(rd.path / "raw" / "r.jsonl") as w:
        w.write({"k": "ұлт"})
    assert json.loads((rd.path / "raw" / "r.jsonl").read_text(encoding="utf-8")) == {"k": "ұлт"}
    assert set(git_state(tmp_path)) == {"commit", "dirty"}
    assert "python" in environment()
