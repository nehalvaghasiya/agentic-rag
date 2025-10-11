"""
Dummy LLM for fallback mode when real language models are unavailable.

Provides template-based responses for debugging and graceful degradation.
This allows the system to continue functioning when API keys are missing or services
are unreachable.
"""

import random
from collections.abc import AsyncIterator

from langchain_core.language_models.llms import LLM
from langchain_core.messages import AIMessage, BaseMessage
from loguru import logger


class DummyLLM(LLM):
    """
    Dummy LLM for fallback mode.

    This class generates template-based responses when real LLM models are unavailable.
    It extracts context from the prompt and generates a coherent fallback response,
    allowing the system to continue functioning for debugging and demonstration purposes.

    Key features:
    1. Extracts retrieved documents from prompt context
    2. Generates informative fallback responses
    3. Supports both sync and async interfaces
    4. Compatible with LangChain's LLM interface

    This is useful for:
    - Development/debugging without API keys
    - Graceful degradation when API is down
    - Testing the RAG pipeline end-to-end
    - Demonstrating the system without real models

    Example:
        >>> llm = DummyLLM()
        >>> response = llm.invoke("What is RAG?")
        >>> # Returns a dummy response explaining that real LLM is unavailable
    """

    @property
    def _llm_type(self) -> str:
        """Return identifier for this LLM type."""
        return "dummy"

    def __init__(self, **kwargs):
        """Initialize dummy LLM."""
        super().__init__(**kwargs)
        logger.warning(
            "Using DUMMY LLM. This is for debugging/fallback only. "
            "Real language model is unavailable."
        )

    def _call(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager=None,
        **kwargs,
    ) -> str:
        """
        Generate a dummy response based on the prompt.

        Args:
            prompt: Input prompt (may contain context from RAG pipeline).
            stop: Stop sequences (ignored for dummy).
            run_manager: Callback manager (ignored for dummy).
            **kwargs: Additional arguments (ignored).

        Returns:
            Dummy response string.
        """
        logger.debug("Generating dummy LLM response")

        # Try to extract query from prompt
        query = self._extract_query(prompt)

        # Generate fallback response
        response = self._generate_dummy_response(query, prompt)

        logger.debug(f"Generated dummy response: {response[:100]}...")
        return response

    def _extract_query(self, prompt: str) -> str:
        """
        Extract the user query from the prompt.

        Args:
            prompt: Full prompt including context.

        Returns:
            Extracted query or placeholder.
        """
        # Try to find query in common prompt formats
        if "Question:" in prompt:
            parts = prompt.split("Question:")
            if len(parts) > 1:
                query = parts[-1].strip().split("\n")[0]
                return query

        if "Query:" in prompt:
            parts = prompt.split("Query:")
            if len(parts) > 1:
                query = parts[-1].strip().split("\n")[0]
                return query

        # Fallback: use last line
        lines = prompt.strip().split("\n")
        return lines[-1] if lines else "your question"

    def _generate_dummy_response(self, query: str, full_prompt: str) -> str:
        """
        Generate a dummy response.

        Args:
            query: Extracted user query.
            full_prompt: Full prompt with context.

        Returns:
            Dummy response string.
        """
        # Check if there's context in the prompt
        has_context = "Context:" in full_prompt or "context:" in full_prompt.lower()

        templates = [
            f"Based on the available information, I can provide insights about '{query}'. "
            f"However, the real language model is currently unavailable. "
            f"This is a dummy response for debugging purposes. "
            f"{'The system retrieved relevant documents from the knowledge base. ' if has_context else ''}"
            f"In a production environment with a real LLM, you would receive a comprehensive "
            f"answer generated from the retrieved context.",
            f"I understand you're asking about '{query}'. "
            f"Please note: This is a FALLBACK RESPONSE because the actual language model is not available. "
            f"{'Your query was matched against documents in the vector store, ' if has_context else ''}"
            f"and in normal operation, those documents would be used to generate a detailed answer. "
            f"For a real response, please configure a valid LLM provider.",
            f"Regarding '{query}': "
            f"The system is operating in FALLBACK MODE (dummy LLM). "
            f"{'Document retrieval is working - relevant chunks were found. ' if has_context else ''}"
            f"However, without access to a real language model, I can only provide this template response. "
            f"To get actual answers, please set up proper LLM API credentials.",
        ]

        return random.choice(templates)

    async def _acall(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager=None,
        **kwargs,
    ) -> str:
        """
        Async version of _call for compatibility.

        Args:
            prompt: Input prompt.
            stop: Stop sequences.
            run_manager: Async callback manager (not used in dummy implementation).
            **kwargs: Additional arguments.

        Returns:
            Dummy response string.
        """
        # Dummy LLM is fast, no need for real async
        # Note: Don't pass async run_manager to sync _call (incompatible types)
        return self._call(prompt, stop, None, **kwargs)


class DummyChatLLM:
    """
    Dummy Chat LLM compatible with LangChain's chat models.

    This provides chat-specific interface for fallback mode.

    Example:
        >>> chat_llm = DummyChatLLM()
        >>> messages = [{"role": "user", "content": "Hello"}]
        >>> response = await chat_llm.ainvoke(messages)
    """

    def __init__(self):
        """Initialize dummy chat LLM."""
        self._llm = DummyLLM()
        logger.warning(
            "Using DUMMY Chat LLM. This is for debugging/fallback only. "
            "Real language model is unavailable."
        )

    def invoke(self, messages: list[BaseMessage], **kwargs) -> AIMessage:
        """
        Invoke with messages (sync).

        Args:
            messages: List of chat messages.
            **kwargs: Additional arguments.

        Returns:
            AI message response.
        """
        # Extract last user message
        user_content = ""
        for msg in reversed(messages):
            if hasattr(msg, "content"):
                user_content = msg.content
                break

        # Ensure user_content is a string
        if isinstance(user_content, list):
            # Handle list of content parts - extract text
            user_content = " ".join(str(part) for part in user_content if part)
        elif not isinstance(user_content, str):
            user_content = str(user_content)

        response = self._llm._call(user_content, **kwargs)
        return AIMessage(content=response)

    async def ainvoke(self, messages: list[BaseMessage], **kwargs) -> AIMessage:
        """
        Async invoke with messages.

        Args:
            messages: List of chat messages.
            **kwargs: Additional arguments.

        Returns:
            AI message response.
        """
        # Use sync version (dummy is fast)
        return self.invoke(messages, **kwargs)

    async def astream(self, messages: list[BaseMessage], **kwargs) -> AsyncIterator[AIMessage]:
        """
        Async stream responses (simulated).

        Args:
            messages: List of chat messages.
            **kwargs: Additional arguments.

        Yields:
            Chunks of AI message.
        """
        response = await self.ainvoke(messages, **kwargs)

        # Simulate streaming by yielding words
        # Ensure response.content is a string before calling split()
        if isinstance(response.content, str):
            words = response.content.split()
        else:
            # Handle non-string content (shouldn't happen with our invoke)
            words = [str(response.content)]

        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield AIMessage(content=chunk)
