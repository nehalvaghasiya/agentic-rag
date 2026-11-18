"""Pure arithmetic; no eval, exec, Python REPL or filesystem access."""

import math

from agentic_rag.models.result import ToolResult
from agentic_rag.models.tool import ToolSpec
from agentic_rag.tools.base import ToolContext


class CalculateTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            "calculate",
            "Basic bounded arithmetic",
            {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                    "operation": {"type": "string"},
                },
                "required": ["a", "b", "operation"],
            },
        )

    async def invoke(self, arguments: dict[str, object], context: ToolContext) -> ToolResult:
        left, right = arguments["a"], arguments["b"]
        if (
            not isinstance(left, (int, float))
            or not isinstance(right, (int, float))
            or isinstance(left, bool)
            or isinstance(right, bool)
        ):
            raise ValueError("Arithmetic operands must be numbers")
        a, b = float(left), float(right)
        op = str(arguments["operation"])
        if not all(math.isfinite(v) and abs(v) < 1e12 for v in (a, b)):
            raise ValueError("Number out of bounds")
        if op not in {"add", "subtract", "multiply", "divide"} or (op == "divide" and b == 0):
            raise ValueError("Unsupported arithmetic")
        value = {
            "add": lambda: a + b,
            "subtract": lambda: a - b,
            "multiply": lambda: a * b,
            "divide": lambda: a / b,
        }[op]()
        if not math.isfinite(value):
            raise ValueError("Non-finite result")
        return ToolResult("calculate", "ok", {"result": value})
