"""Tool definitions, calls, and built-in deterministic tools."""

from __future__ import annotations

import ast
import json
import operator
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class ToolError(ValueError):
    """Raised for malformed arguments or failed tool execution."""


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, str]  # argument name -> description (all required)
    fn: Callable[..., Any]

    def run(self, arguments: dict[str, Any]) -> str:
        missing = set(self.parameters) - set(arguments)
        extra = set(arguments) - set(self.parameters)
        if missing or extra:
            raise ToolError(f"{self.name}: missing {sorted(missing)}, unexpected {sorted(extra)}")
        return str(self.fn(**arguments))

    def signature(self) -> str:
        args = ", ".join(f'"{k}": <{v}>' for k, v in self.parameters.items())
        return f"- {self.name}: {self.description} Arguments: {{{args}}}"


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    raw: str
    malformed: bool = False
    result: str | None = None
    error: str | None = None


@dataclass
class ToolTrace:
    calls: list[ToolCall] = field(default_factory=list)
    responses: list[str] = field(default_factory=list)
    final_text: str = ""
    last_output: Any = None  # GenerationOutput of the final step


# ----------------------------------------------------------------- built-ins
_OPS: dict[type, Callable[..., Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_eval(expression: str) -> float:
    """Evaluate an arithmetic expression without ``eval`` (numbers and + - * / // % ** only)."""
    expression = expression.replace("×", "*").replace("÷", "/").replace("^", "**")

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ToolError("exponent too large")
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ToolError(f"unsupported expression element: {ast.dump(node)[:40]}")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ToolError(f"invalid expression: {expression!r}") from exc
    try:
        return ev(tree)
    except ZeroDivisionError as exc:
        raise ToolError("division by zero") from exc


def _format_number(x: float) -> str:
    x = round(float(x), 6)
    return str(int(x)) if x.is_integer() else f"{x:.6f}".rstrip("0").rstrip(".")


def calculator(expression: str) -> str:
    return _format_number(safe_eval(str(expression)))


_UNITS = {
    "km": ("m", 1000.0),
    "m": ("m", 1.0),
    "cm": ("m", 0.01),
    "mm": ("m", 0.001),
    "mi": ("m", 1609.344),
    "ft": ("m", 0.3048),
    "in": ("m", 0.0254),
    "kg": ("g", 1000.0),
    "g": ("g", 1.0),
    "lb": ("g", 453.59237),
    "l": ("l", 1.0),
    "ml": ("l", 0.001),
}


_UNIT_ALIASES = {
    "kilometre": "km",
    "kilometer": "km",
    "kilometres": "km",
    "kilometers": "km",
    "metre": "m",
    "meter": "m",
    "metres": "m",
    "meters": "m",
    "centimetre": "cm",
    "centimeter": "cm",
    "centimetres": "cm",
    "centimeters": "cm",
    "millimetre": "mm",
    "millimeter": "mm",
    "millimetres": "mm",
    "millimeters": "mm",
    "mile": "mi",
    "miles": "mi",
    "foot": "ft",
    "feet": "ft",
    "inch": "in",
    "inches": "in",
    "kilogram": "kg",
    "kilograms": "kg",
    "gram": "g",
    "grams": "g",
    "pound": "lb",
    "pounds": "lb",
    "lbs": "lb",
    "litre": "l",
    "liter": "l",
    "litres": "l",
    "liters": "l",
    "millilitre": "ml",
    "milliliter": "ml",
    "millilitres": "ml",
    "milliliters": "ml",
    "celsius": "c",
    "fahrenheit": "f",
    "°c": "c",
    "°f": "f",
}


def _unit(name: str) -> str:
    key = str(name).strip().lower()
    return _UNIT_ALIASES.get(key, key)


def unit_convert(value: float, from_unit: str, to_unit: str) -> str:
    f, t = _unit(from_unit), _unit(to_unit)
    if {f, t} <= {"c", "f"}:
        v = float(value)
        return _format_number(v if f == t else (v * 9 / 5 + 32 if f == "c" else (v - 32) * 5 / 9))
    if f not in _UNITS or t not in _UNITS or _UNITS[f][0] != _UNITS[t][0]:
        raise ToolError(f"cannot convert {from_unit} to {to_unit}")
    return _format_number(float(value) * _UNITS[f][1] / _UNITS[t][1])


BUILTIN_TOOLS: dict[str, Tool] = {
    "calculator": Tool(
        "calculator",
        "Evaluates an arithmetic expression exactly.",
        {"expression": "arithmetic expression, e.g. 17*23+4"},
        calculator,
    ),
    "unit_convert": Tool(
        "unit_convert",
        "Converts a value between units. Supported units: km, m, cm, mm, mi, ft, in (length); "
        "kg, g, lb (mass); l, ml (volume); c, f (temperature). Full names are also accepted.",
        {"value": "number", "from_unit": "unit", "to_unit": "unit"},
        unit_convert,
    ),
}

_CALL_RE = re.compile(r"TOOL_CALL:\s*(\{.*\})", re.DOTALL)


def parse_tool_call(text: str) -> ToolCall | None:
    """Parse ``TOOL_CALL: {"name": ..., "arguments": {...}}`` from a model response."""
    m = _CALL_RE.search(text)
    if not m:
        return None
    raw = m.group(1)
    # Take the longest prefix ending in '}' that parses as JSON (models often add text after
    # the call).
    for end in range(len(raw), 0, -1):
        if raw[end - 1] != "}":
            continue
        try:
            obj = json.loads(raw[:end])
        except json.JSONDecodeError:
            continue
        if (
            isinstance(obj, dict)
            and isinstance(obj.get("name"), str)
            and isinstance(obj.get("arguments", {}), dict)
        ):
            return ToolCall(obj["name"], obj.get("arguments", {}), raw[:end])
        break
    return ToolCall("", {}, raw, malformed=True)
