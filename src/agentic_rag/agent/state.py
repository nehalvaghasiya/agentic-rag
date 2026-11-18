"""Checkpoint state contains serializable task data, never provider clients or identities."""

from typing import TypedDict


class AgentState(TypedDict, total=False):
    run_id: str
    goals: list[str]
    evidence_ids: list[str]
    observations: list[dict[str, object]]
    answer: str
    skill: str
    iteration: int
    sufficient: bool
    missing: str
