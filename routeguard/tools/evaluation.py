"""Tool-use failure taxonomy.

A tool-use case (JSONL, see ``benchmarks/samples/tool_use.jsonl``) specifies the
question, the gold answer, which tools are *required* (possibly none), and the
expected tool results. Each agent trace is labelled with zero or more of:

``missing_required_call``  a required tool was never called
``unnecessary_call``       a tool was called although none was required
``wrong_tool``             a tool other than the required ones was called
``malformed_arguments``    unparseable call, unknown tool, or invalid arguments
``ignored_result``         the last tool result was correct but the final answer is missing
                           or not derived from it
``contradicted_result``    the last tool result was correct but the final (numeric) answer
                           states a different value
``fabricated_result``      the model wrote ``TOOL_RESULT`` itself or claimed a tool output
                           without calling the tool
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from routeguard.answers import canonical_number, extract_answer
from routeguard.evaluation.scoring import score_prediction
from routeguard.tools.base import ToolTrace
from routeguard.types import AnswerType, Query

TOOL_FAILURES = (
    "missing_required_call",
    "unnecessary_call",
    "wrong_tool",
    "malformed_arguments",
    "ignored_result",
    "contradicted_result",
    "fabricated_result",
)
_CLAIM = re.compile(
    r"(the )?(calculator|tool|converter) (returned|returns|says|gave|output)", re.IGNORECASE
)


class ToolCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    answer: str
    answer_type: str = "numeric"
    tools: list[str] = Field(default_factory=lambda: ["calculator", "unit_convert"])
    required_tools: list[str] = Field(default_factory=list)
    expected_calls: list[dict[str, Any]] = Field(
        default_factory=list, description="for the simulator only"
    )
    source: str = "tool-use-fixture"
    license: str = "CC0-1.0"

    def to_query(self) -> Query:
        return Query(
            text=self.question,
            id=self.id,
            answer_type=AnswerType(self.answer_type),
            category="tool_use",
            reference={
                "id": self.id,
                "answer": self.answer,
                "answer_type": self.answer_type,
                "expected_calls": self.expected_calls,
                "required_tools": self.required_tools,
            },
        )


def label_trace(case: ToolCase, trace: ToolTrace) -> dict[str, Any]:
    labels: list[str] = []
    called = [c.name for c in trace.calls if not c.malformed]
    required = set(case.required_tools)
    if required - set(called):
        labels.append("missing_required_call")
    if not required and trace.calls:
        labels.append("unnecessary_call")
    if required and any(n not in required for n in called):
        labels.append("wrong_tool")
    if any(c.malformed or c.error for c in trace.calls):
        labels.append("malformed_arguments")

    final = trace.final_text
    answer_type = AnswerType(case.answer_type)
    answer = extract_answer(final, answer_type)
    results = [c.result for c in trace.calls if c.result is not None]
    # Result-use failures are judged only when the last tool result *is* the correct
    # answer, so legitimate intermediate tool calls are not penalised.
    if (
        results
        and score_prediction(results[-1], case.answer, answer_type).correct
        and not score_prediction(answer, case.answer, answer_type).correct
    ):
        numeric_answer = answer is not None and canonical_number(answer) is not None
        labels.append("contradicted_result" if numeric_answer else "ignored_result")
    model_text = "\n".join(trace.responses)
    if "TOOL_RESULT" in model_text or (not trace.calls and _CLAIM.search(model_text)):
        labels.append("fabricated_result")
    correct = score_prediction(answer, case.answer, answer_type).correct
    return {
        "id": case.id,
        "labels": labels,
        "correct": correct,
        "answer": answer,
        "n_calls": len(trace.calls),
        "tools_called": called,
    }


def summarize_tool_eval(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(lab for r in rows for lab in r["labels"])
    n = len(rows)
    return {
        "n": n,
        "accuracy": sum(r["correct"] for r in rows) / n if n else float("nan"),
        "failure_rates": {k: counts.get(k, 0) / n if n else float("nan") for k in TOOL_FAILURES},
        "calls_mean": sum(r["n_calls"] for r in rows) / n if n else float("nan"),
    }
