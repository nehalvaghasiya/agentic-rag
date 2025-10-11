"""
Comprehensive tests for DummyLLM and DummyChatLLM classes.

Tests fallback mode LLM with template-based response generation.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from rag.backend.llm.dummy_llm import DummyChatLLM, DummyLLM


class TestDummyLLMInitialization:
    """Test DummyLLM initialization."""

    def test_init_creates_instance(self):
        """Test that DummyLLM can be instantiated."""
        llm = DummyLLM()
        assert llm is not None
        assert llm._llm_type == "dummy"

    def test_llm_type_property(self):
        """Test _llm_type property returns correct identifier."""
        llm = DummyLLM()
        assert llm._llm_type == "dummy"


class TestDummyLLMResponseGeneration:
    """Test DummyLLM response generation."""

    def test_call_generates_response(self):
        """Test that _call generates a non-empty response."""
        llm = DummyLLM()
        response = llm._call("What is RAG?")

        assert isinstance(response, str)
        assert len(response) > 0

    def test_response_mentions_fallback(self):
        """Test that response mentions it's a dummy/fallback response."""
        llm = DummyLLM()
        response = llm._call("Test question")

        # Should mention dummy/fallback status
        assert any(
            keyword in response.lower()
            for keyword in ["dummy", "fallback", "unavailable", "debugging"]
        )

    def test_response_includes_query(self):
        """Test that response includes the user query."""
        llm = DummyLLM()
        query = "What is machine learning?"
        response = llm._call(query)

        # Should reference the query somehow
        assert "machine learning" in response or "your question" in response.lower()

    def test_different_prompts_produce_responses(self):
        """Test various prompt formats produce valid responses."""
        llm = DummyLLM()
        prompts = [
            "Simple question",
            "Question: What is AI?",
            "Query: Explain RAG",
            "Context: Some context\n\nQuestion: Answer this",
        ]

        for prompt in prompts:
            response = llm._call(prompt)
            assert isinstance(response, str)
            assert len(response) > 50  # Should be substantial


class TestQueryExtraction:
    """Test query extraction from prompts."""

    def test_extract_query_with_question_marker(self):
        """Test extracting query with 'Question:' marker."""
        llm = DummyLLM()
        prompt = "Context: Some context\n\nQuestion: What is RAG?"
        query = llm._extract_query(prompt)

        assert "What is RAG?" in query or query == "What is RAG?"

    def test_extract_query_with_query_marker(self):
        """Test extracting query with 'Query:' marker."""
        llm = DummyLLM()
        prompt = "Some text\nQuery: Explain this concept"
        query = llm._extract_query(prompt)

        assert "Explain this concept" in query

    def test_extract_query_fallback_to_last_line(self):
        """Test fallback to last line when no markers found."""
        llm = DummyLLM()
        prompt = "Line 1\nLine 2\nLine 3 is the question"
        query = llm._extract_query(prompt)

        assert query == "Line 3 is the question"

    def test_extract_query_empty_prompt(self):
        """Test extraction from empty prompt."""
        llm = DummyLLM()
        query = llm._extract_query("")

        # Empty prompt returns empty string from last line
        assert query == ""


class TestResponseGeneration:
    """Test _generate_dummy_response method."""

    def test_response_with_context(self):
        """Test response generation when context is present."""
        llm = DummyLLM()
        query = "Test query"
        full_prompt = "Context: Some relevant context\n\nQuestion: Test query"

        response = llm._generate_dummy_response(query, full_prompt)

        assert isinstance(response, str)
        assert len(response) > 0
        # Should mention documents/retrieval since context is present
        assert any(
            keyword in response.lower()
            for keyword in ["document", "retrieve", "context", "knowledge"]
        )

    def test_response_without_context(self):
        """Test response generation without context."""
        llm = DummyLLM()
        query = "Test query"
        full_prompt = "Question: Test query"

        response = llm._generate_dummy_response(query, full_prompt)

        assert isinstance(response, str)
        assert len(response) > 0

    def test_response_variability(self):
        """Test that responses vary (random template selection)."""
        llm = DummyLLM()
        query = "Same query"
        full_prompt = "Question: Same query"

        # Generate multiple responses
        responses = {llm._generate_dummy_response(query, full_prompt) for _ in range(20)}

        # Should have multiple different responses due to random.choice
        assert len(responses) > 1


class TestAsyncMethods:
    """Test async LLM methods."""

    @pytest.mark.asyncio
    async def test_acall_generates_response(self):
        """Test async _acall generates response."""
        llm = DummyLLM()
        response = await llm._acall("What is AI?")

        assert isinstance(response, str)
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_acall_matches_sync(self):
        """Test that async produces same type of response as sync."""
        llm = DummyLLM()
        prompt = "Test prompt"

        sync_response = llm._call(prompt)
        async_response = await llm._acall(prompt)

        # Both should be strings with content
        assert isinstance(sync_response, str)
        assert isinstance(async_response, str)
        assert len(sync_response) > 0
        assert len(async_response) > 0


class TestDummyChatLLMInitialization:
    """Test DummyChatLLM initialization."""

    def test_init_creates_instance(self):
        """Test that DummyChatLLM can be instantiated."""
        chat_llm = DummyChatLLM()
        assert chat_llm is not None
        assert hasattr(chat_llm, "_llm")
        assert isinstance(chat_llm._llm, DummyLLM)


class TestDummyChatLLMInvoke:
    """Test DummyChatLLM invoke method."""

    def test_invoke_with_single_message(self):
        """Test invoke with single human message."""
        chat_llm = DummyChatLLM()
        messages = [HumanMessage(content="What is RAG?")]

        response = chat_llm.invoke(messages)

        assert isinstance(response, AIMessage)
        assert isinstance(response.content, str)
        assert len(response.content) > 0

    def test_invoke_with_multiple_messages(self):
        """Test invoke with conversation history."""
        chat_llm = DummyChatLLM()
        messages = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="What is AI?"),
            AIMessage(content="AI is artificial intelligence."),
            HumanMessage(content="Tell me more."),
        ]

        response = chat_llm.invoke(messages)

        assert isinstance(response, AIMessage)
        assert len(response.content) > 0
        # Should use the last human message
        assert "more" in response.content.lower() or "dummy" in response.content.lower()

    def test_invoke_returns_ai_message(self):
        """Test that invoke returns AIMessage type."""
        chat_llm = DummyChatLLM()
        messages = [HumanMessage(content="Test")]

        response = chat_llm.invoke(messages)

        assert type(response) == AIMessage


class TestDummyChatLLMAsyncInvoke:
    """Test DummyChatLLM async invoke."""

    @pytest.mark.asyncio
    async def test_ainvoke_with_messages(self):
        """Test async invoke with messages."""
        chat_llm = DummyChatLLM()
        messages = [HumanMessage(content="What is machine learning?")]

        response = await chat_llm.ainvoke(messages)

        assert isinstance(response, AIMessage)
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_ainvoke_matches_sync(self):
        """Test that ainvoke produces same type as invoke."""
        chat_llm = DummyChatLLM()
        messages = [HumanMessage(content="Test query")]

        sync_response = chat_llm.invoke(messages)
        async_response = await chat_llm.ainvoke(messages)

        assert type(sync_response) == type(async_response)
        assert isinstance(sync_response, AIMessage)
        assert isinstance(async_response, AIMessage)


class TestDummyChatLLMStreaming:
    """Test DummyChatLLM streaming."""

    @pytest.mark.asyncio
    async def test_astream_yields_chunks(self):
        """Test that astream yields message chunks."""
        chat_llm = DummyChatLLM()
        messages = [HumanMessage(content="Short query")]

        chunks = []
        async for chunk in chat_llm.astream(messages):
            chunks.append(chunk)
            assert isinstance(chunk, AIMessage)

        # Should have multiple chunks (simulated word-by-word streaming)
        assert len(chunks) > 1

    @pytest.mark.asyncio
    async def test_astream_chunks_combine_to_full_response(self):
        """Test that streaming chunks combine to correct length."""
        chat_llm = DummyChatLLM()
        messages = [HumanMessage(content="Test")]

        # Collect streamed chunks
        streamed_chunks = []
        async for chunk in chat_llm.astream(messages):
            streamed_chunks.append(chunk)

        # Should have multiple chunks (word-by-word streaming)
        assert len(streamed_chunks) > 1

        # Combine all chunks
        streamed_content = "".join([chunk.content for chunk in streamed_chunks])

        # Should have substantial content
        assert len(streamed_content) > 50

    @pytest.mark.asyncio
    async def test_astream_with_empty_message(self):
        """Test streaming with empty message."""
        chat_llm = DummyChatLLM()
        messages = [HumanMessage(content="")]

        chunks = []
        async for chunk in chat_llm.astream(messages):
            chunks.append(chunk)

        # Should still produce chunks
        assert len(chunks) > 0


class TestEdgeCases:
    """Test edge cases for DummyLLM."""

    def test_very_long_prompt(self):
        """Test with very long prompt."""
        llm = DummyLLM()
        long_prompt = "Context: " + ("This is context. " * 1000) + "\n\nQuestion: Answer this"

        response = llm._call(long_prompt)

        assert isinstance(response, str)
        assert len(response) > 0

    def test_empty_prompt(self):
        """Test with empty prompt."""
        llm = DummyLLM()
        response = llm._call("")

        assert isinstance(response, str)
        assert len(response) > 0

    def test_special_characters_in_prompt(self):
        """Test with special characters."""
        llm = DummyLLM()
        prompt = "Question: What about @#$%^&*()?"

        response = llm._call(prompt)

        assert isinstance(response, str)
        assert len(response) > 0

    def test_unicode_in_prompt(self):
        """Test with Unicode characters."""
        llm = DummyLLM()
        prompt = "Question: Что такое RAG? 什么是RAG? 🤖"

        response = llm._call(prompt)

        assert isinstance(response, str)
        assert len(response) > 0

    def test_multiline_query(self):
        """Test with multiline query."""
        llm = DummyLLM()
        prompt = """Question: This is a question
        that spans multiple
        lines"""

        response = llm._call(prompt)

        assert isinstance(response, str)
        assert len(response) > 0


class TestStopSequences:
    """Test handling of stop sequences."""

    def test_call_with_stop_sequences(self):
        """Test _call with stop sequences (should be ignored)."""
        llm = DummyLLM()
        response = llm._call("Question: Test", stop=["END", "STOP"])

        # Should still generate response (stop sequences ignored for dummy)
        assert isinstance(response, str)
        assert len(response) > 0

    def test_call_with_empty_stop_list(self):
        """Test with empty stop list."""
        llm = DummyLLM()
        response = llm._call("Question: Test", stop=[])

        assert isinstance(response, str)
        assert len(response) > 0


class TestChatLLMEdgeCases:
    """Test edge cases for DummyChatLLM."""

    def test_invoke_with_empty_messages(self):
        """Test invoke with empty messages list."""
        chat_llm = DummyChatLLM()
        response = chat_llm.invoke([])

        assert isinstance(response, AIMessage)
        # Should still generate response even with empty input

    def test_invoke_with_system_message_only(self):
        """Test invoke with only system message."""
        chat_llm = DummyChatLLM()
        messages = [SystemMessage(content="You are an assistant.")]

        response = chat_llm.invoke(messages)

        assert isinstance(response, AIMessage)

    def test_invoke_with_kwargs(self):
        """Test that invoke accepts and ignores kwargs."""
        chat_llm = DummyChatLLM()
        messages = [HumanMessage(content="Test")]

        # Should not raise error with extra kwargs
        response = chat_llm.invoke(
            messages, temperature=0.7, max_tokens=100, custom_param="value"
        )

        assert isinstance(response, AIMessage)

    @pytest.mark.asyncio
    async def test_ainvoke_with_kwargs(self):
        """Test that ainvoke accepts and ignores kwargs."""
        chat_llm = DummyChatLLM()
        messages = [HumanMessage(content="Test")]

        response = await chat_llm.ainvoke(messages, temperature=0.5)

        assert isinstance(response, AIMessage)
