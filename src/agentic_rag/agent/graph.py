"""The compiled complex executor. Direct and fast RAG never enter this graph."""

from typing import TYPE_CHECKING, Any

from agentic_rag.agent.state import AgentState

if TYPE_CHECKING:
    from agentic_rag.agent.service import AgentService


def build_graph(service: "AgentService", checkpointer: Any = None) -> Any:
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(AgentState)
    graph.add_node("plan", service.plan_node)
    graph.add_node("research", service.research_node)
    graph.add_node("synthesize", service.synth_node)
    graph.add_node("verify", service.verify_node)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "research")
    graph.add_edge("research", "synthesize")
    graph.add_edge("synthesize", "verify")
    graph.add_conditional_edges(
        "verify", service.next_node, {"research": "research", "finish": END}
    )
    return graph.compile(checkpointer=checkpointer)
