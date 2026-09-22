"""Prompt construction.

A prompt is assembled from three independent parts:

* a *reasoning instruction* chosen from the **predicted** task category
  (so task-classification errors propagate, which is what the ablation measures),
* a *format instruction* chosen from the answer type (needed to parse the output),
* a *strategy* modifier (``default``, ``careful`` for re-prompting, ``rag`` with evidence).

Instructions are in English for every query language. This is a deliberate,
documented choice (see docs/multilingual.md): it keeps the prompt constant across
languages so that language effects are attributable to the query itself.
"""

from __future__ import annotations

from routeguard.types import AnswerType, Message, Query

SYSTEM_PROMPT = "You are a careful, accurate assistant."

REASONING = {
    "math": "Solve the problem step by step, showing the intermediate calculations.",
    "logic": "Reason through the problem step by step before answering.",
    "coding": "Write a correct, self-contained Python solution.",
    "reading_comprehension": "Read the passage carefully and answer using only its content.",
    "science": "Use relevant scientific knowledge and reason briefly before answering.",
    "factual_qa": "Answer the question accurately and concisely.",
    "summarization": "Summarise the text faithfully without adding information.",
    "extraction": "Extract exactly the requested information from the text.",
    "translation": "Translate the text faithfully.",
    "classification": "Classify the text into the single most appropriate category.",
    "retrieval": "Answer using the provided evidence where possible.",
    "tool_use": "Decide whether a tool is needed, then answer.",
}
DEFAULT_REASONING = "Think briefly, then answer."

FORMAT = {
    AnswerType.NUMERIC: "End your response with a final line of the form 'Final answer: <number>'.",
    AnswerType.CHOICE: (
        "Choose the single best option. End your response with a final line of the form "
        "'Final answer: <letter>'."
    ),
    AnswerType.CODE: (
        "Return the complete solution in a single ```python code block. Keep the requested "
        "function name and signature."
    ),
    AnswerType.TEXT: (
        "Keep the answer short (a few words). End your response with a final line of the form "
        "'Final answer: <answer>'."
    ),
}

CAREFUL = (
    "This question may be harder than it looks. Work through it slowly, check each step, "
    "and correct any mistake before giving the final answer."
)


def format_choices(choices: list[str]) -> str:
    letters = "ABCDEFGHIJ"
    return "\n".join(f"{letters[i]}. {c}" for i, c in enumerate(choices))


def build_messages(
    query: Query,
    category: str,
    strategy: str = "default",
    evidence: list[str] | None = None,
) -> list[Message]:
    """Build chat messages for ``query`` given the predicted ``category``."""
    parts: list[str] = [REASONING.get(category, DEFAULT_REASONING)]
    if strategy == "careful":
        parts.append(CAREFUL)
    parts.append(FORMAT[query.answer_type])
    instruction = " ".join(parts)

    body: list[str] = []
    if evidence:
        numbered = "\n\n".join(f"[{i + 1}] {e}" for i, e in enumerate(evidence))
        body.append(
            "Evidence (may be incomplete or irrelevant; say so if it does not contain the "
            "answer):\n" + numbered
        )
    if query.context:
        body.append(f"Passage:\n{query.context}")
    body.append(f"Question:\n{query.text}")
    if query.choices:
        body.append(f"Options:\n{format_choices(query.choices)}")
    user = "\n\n".join(body) + f"\n\n{instruction}"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def difficulty_judge_messages(query: Query) -> list[Message]:
    """Prompt for the LLM-as-difficulty-judge baseline (Baseline D)."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Rate how difficult the following question is for a small language model to answer "
                "correctly, on a scale from 1 (trivial) to 10 (very hard). Do not answer the "
                "question. Reply with only the number.\n\nQuestion:\n" + query.text
            ),
        },
    ]


def verification_judge_messages(query: Query, answer_text: str) -> list[Message]:
    """Prompt for the second-model judge verifier."""
    options = f"\n\nOptions:\n{format_choices(query.choices)}" if query.choices else ""
    passage = f"Passage:\n{query.context}\n\n" if query.context else ""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"{passage}Question:\n{query.text}{options}\n\n"
                f"Proposed response:\n{answer_text}\n\n"
                "Is the proposed final answer correct? Check it independently. "
                "Reply with a single word: Yes or No."
            ),
        },
    ]


def judge_select_messages(query: Query, candidates: list[str]) -> list[Message]:
    """Prompt asking a (stronger) model to adjudicate between candidate answers."""
    listed = "\n".join(f"- Candidate {i + 1}: {c}" for i, c in enumerate(candidates))
    msgs = build_messages(query, category="general")
    msgs[-1]["content"] += (
        f"\n\nSeveral previous attempts proposed these final answers:\n{listed}\n"
        "They may all be wrong. Solve the problem yourself, then give your own final answer "
        "in the required format."
    )
    return msgs
