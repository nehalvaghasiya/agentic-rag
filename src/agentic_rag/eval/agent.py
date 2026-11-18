"""Bounded trajectory, task completion and loop diagnostics."""


class AgentMetrics:
    def score(
        self, events: list[dict[str, object]], max_tools: int, completed: bool, supported: bool
    ) -> dict[str, float]:
        tool_starts = sum(e.get("type") == "tool_started" for e in events)
        denied = sum(e.get("type") == "tool_denied" for e in events)
        loops = sum(e.get("type") == "loop_detected" for e in events)
        return {
            "supported_completion": float(completed and supported),
            "loop_rate": float(loops > 0),
            "tool_budget_compliance": float(tool_starts <= max_tools),
            "tool_denial_count": float(denied),
            "tool_calls": float(tool_starts),
        }
