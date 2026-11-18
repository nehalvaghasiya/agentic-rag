"""Low-cardinality Prometheus metrics, no tenant IDs or source text as labels."""

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest


class Metrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        self.requests = Counter(
            "rag_requests_total",
            "Requests by mode/outcome",
            ["mode", "outcome"],
            registry=self.registry,
        )
        self.latency = Histogram(
            "rag_request_seconds",
            "End-to-end request duration",
            ["mode"],
            registry=self.registry,
            buckets=(0.005, 0.02, 0.05, 0.1, 0.25, 0.5, 1, 3, 10, 30, 60),
        )
        self.tools = Counter(
            "rag_tools_total", "Tool invocations", ["name", "status"], registry=self.registry
        )
        self.ingest = Counter(
            "rag_ingest_total", "Ingest outcomes", ["outcome"], registry=self.registry
        )

    def observe(self, mode: str, outcome: str, seconds: float) -> None:
        if mode not in {"auto", "baseline", "advanced", "agentic"}:
            mode = "other"
        self.requests.labels(mode, outcome if outcome in {"ok", "error"} else "error").inc()
        self.latency.labels(mode).observe(seconds)

    def export(self) -> bytes:
        return generate_latest(self.registry)
