"""Checkpoint abstraction for offline process-only replay; NOT durable storage."""

from agentic_rag.data.fake import FakeStore
from agentic_rag.models.principal import Principal


class CheckpointStore:
    def __init__(self, store: FakeStore) -> None:
        self.store = store
        self._states: dict[str, dict[str, object]] = {}

    def save(self, run_id: str, principal: Principal, state: dict[str, object]) -> None:
        self.store.run_for(run_id, principal)
        self._states[run_id] = state.copy()

    def load(self, run_id: str, principal: Principal) -> dict[str, object] | None:
        self.store.run_for(run_id, principal)
        value = self._states.get(run_id)
        return value.copy() if value else None
