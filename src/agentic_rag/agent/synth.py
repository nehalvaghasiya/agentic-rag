"""Generate answers from verified evidence or abstain explicitly."""

from agentic_rag.models.evidence import Evidence
from agentic_rag.providers.chat import ChatModel


class Synthesizer:
    def __init__(self, chat: ChatModel) -> None:
        self.chat = chat

    async def generate(self, question: str, evidence: list[Evidence]) -> str:
        if not evidence:
            return "I cannot answer from the available authorized sources."
        return await self.chat.generate(question, evidence)

    def abstain(self) -> str:
        return "I cannot verify an answer from the available authorized sources."
