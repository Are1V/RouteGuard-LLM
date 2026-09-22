"""Benchmark item schema (one JSON object per line in ``*.jsonl`` files).

The same schema is used for converted public datasets and for manually curated
items, so a curated Kazakh or Dari set is just a JSONL file (see
docs/adding_datasets.md and ``benchmarks/samples/curated_template.jsonl``).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from routeguard.types import AnswerType, Query


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    answer: str | list[str]
    answer_type: AnswerType
    category: str
    language: str = Field(description="ISO 639-1 code of the query language, e.g. en, kk, ru, fa")
    language_variant: str | None = Field(None, description="e.g. prs_Arab (Dari) vs pes_Arab")
    choices: list[str] | None = None
    context: str | None = None
    public_tests: list[str] | None = Field(None, description="tests shown to the model")
    eval_tests: list[str] | None = Field(None, description="tests used only for scoring")
    entry_point: str | None = None
    solution: str | None = Field(None, description="reference solution (code tasks)")
    parallel_id: str | None = Field(None, description="shared by translations of the same item")
    source: str = "custom"
    license: str = "unspecified"
    difficulty: float | None = Field(None, ge=0, le=1, description="annotated prior, optional")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _consistent(self) -> Item:
        if self.answer_type == AnswerType.CHOICE:
            if not self.choices:
                raise ValueError(f"{self.id}: choice items need 'choices'")
            letters = "ABCDEFGHIJ"[: len(self.choices)]
            answers = self.answer if isinstance(self.answer, list) else [self.answer]
            if any(a not in letters for a in answers):
                raise ValueError(f"{self.id}: choice answers must be letters in {letters!r}")
        if self.answer_type == AnswerType.CODE and not self.eval_tests:
            raise ValueError(f"{self.id}: code items need 'eval_tests'")
        return self

    def to_query(self) -> Query:
        """Convert to a pipeline query. Gold data goes only into ``reference``."""
        return Query(
            text=self.question,
            id=self.id,
            language=self.language,
            category=self.category,
            answer_type=self.answer_type,
            choices=self.choices,
            context=self.context,
            public_tests=self.public_tests,
            entry_point=self.entry_point,
            reference={
                "id": self.id,
                "answer": self.answer,
                "answer_type": self.answer_type.value,
                "choices": self.choices,
                "difficulty": self.difficulty,
                "language": self.language,
                "category": self.category,
                "solution": self.solution,
                "entry_point": self.entry_point,
                "context": self.context or self.metadata.get("gold_passage"),
            },
            metadata={"source": self.source, "language_variant": self.language_variant},
        )
