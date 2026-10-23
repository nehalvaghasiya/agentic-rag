"""Keep server instructions separate from client dialogue and retrieved text."""

from typing import assert_never

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from backend.config import Prompts
from backend.models import ChatMessage


def build_chat_messages(history: list[ChatMessage]) -> list[BaseMessage]:
    """Preserve the complete validated conversation after one trusted policy."""
    messages: list[BaseMessage] = [SystemMessage(content=Prompts.CHAT_SYSTEM)]
    for message in history:
        if message.role == "user":
            messages.append(HumanMessage(content=message.content))
        elif message.role == "assistant":
            messages.append(AIMessage(content=message.content))
        else:
            assert_never(message.role)
    return messages


def build_task_messages(instructions: str, data: str) -> list[BaseMessage]:
    """Only server constants belong in instructions; all task data stays human."""
    return [
        SystemMessage(content=f"{Prompts.RAG_DATA_POLICY}\n\n{instructions}"),
        HumanMessage(content=data),
    ]


def build_answer_messages(question: str, docs: list[Document]) -> list[BaseMessage]:
    """Build identical RAG policy and context for invoke and streaming generation."""
    context_parts = []
    for index, doc in enumerate(docs[:5], 1):
        source = doc.metadata.get("source", "unknown")
        context_parts.append(f"[{index}] Source: {source}\n{doc.page_content}")
    context = "\n\n".join(context_parts)
    return build_task_messages(Prompts.ANSWER, f"Question: {question}\n\nContext:\n{context}")
