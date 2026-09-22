"""A minimal, backend-agnostic tool-calling loop.

The protocol is plain text so it works with any chat model (no native
function-calling API required): the model emits one line
``TOOL_CALL: {"name": ..., "arguments": {...}}``; the agent executes the tool and
replies with ``TOOL_RESULT: ...``; the model finishes with ``Final answer: ...``.
Only the agent ever writes ``TOOL_RESULT``, which is what makes fabricated tool
results detectable.
"""

from __future__ import annotations

from routeguard.context import CallContext
from routeguard.prompts import FORMAT, SYSTEM_PROMPT
from routeguard.tools.base import Tool, ToolError, ToolTrace, parse_tool_call
from routeguard.types import Message, Query


def tool_messages(query: Query, tools: list[Tool]) -> list[Message]:
    listing = "\n".join(t.signature() for t in tools)
    instructions = (
        "You can use these tools:\n" + listing + "\n\nTo use a tool, reply with exactly one line:\n"
        'TOOL_CALL: {"name": "<tool>", "arguments": {...}}\n'
        "and wait for the TOOL_RESULT. Use a tool only if it is needed. Never write TOOL_RESULT "
        "yourself. " + FORMAT[query.answer_type]
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{instructions}\n\nQuestion:\n{query.text}"},
    ]


class ToolAgent:
    def __init__(self, tools: list[Tool], max_steps: int = 3):
        self.tools = {t.name: t for t in tools}
        self.max_steps = max_steps

    def run(self, query: Query, model: str, ctx: CallContext) -> ToolTrace:
        messages = tool_messages(query, list(self.tools.values()))
        trace = ToolTrace()
        for step in range(self.max_steps + 1):
            out = ctx.generate(
                model,
                messages,
                purpose="tool_agent",
                metadata={"tool_step": step, "tool_results": [c.result for c in trace.calls]},
            )
            trace.responses.append(out.text)
            call = parse_tool_call(out.text) if step < self.max_steps else None
            if call is None:
                trace.final_text = out.text
                trace.last_output = out
                return trace
            trace.calls.append(call)
            if call.malformed:
                call.error = "malformed tool call"
                reply = (
                    "TOOL_RESULT: error: malformed tool call (expected JSON with name/arguments)"
                )
            elif call.name not in self.tools:
                call.error = f"unknown tool {call.name!r}"
                reply = f"TOOL_RESULT: error: unknown tool {call.name!r}"
            else:
                try:
                    call.result = self.tools[call.name].run(call.arguments)
                    reply = f"TOOL_RESULT: {call.result}"
                except (ToolError, TypeError, ValueError) as exc:
                    call.error = str(exc)
                    reply = f"TOOL_RESULT: error: {exc}"
            messages = [
                *messages,
                {"role": "assistant", "content": out.text},
                {"role": "user", "content": reply},
            ]
        return trace  # pragma: no cover - loop always returns at the last step
