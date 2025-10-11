"""
LLM provider implementations with async support.

Supports OpenAI, Cohere, HuggingFace, and custom OpenAI-compatible endpoints.
All API-based LLMs are async to prevent blocking during generation.

Includes fallback mode for graceful degradation when models are unavailable.
"""

from langchain_cohere import ChatCohere
from langchain_community.chat_models import ChatOpenAI
from langchain_huggingface import HuggingFaceEndpoint
from loguru import logger

from rag.backend.llm.dummy_llm import DummyChatLLM
from rag.config import LLMConfig, get_api_key


def create_llm(config: LLMConfig, fallback_config=None):
    """
    Factory function to create LLM based on configuration.

    All LLM providers support async streaming for better UX:
    - Async prevents blocking during generation (which can take 5-30+ seconds)
    - Streaming allows incremental token display to users
    - Multiple concurrent user queries can be handled efficiently

    Includes fallback mode: If the real LLM is unavailable (missing API key,
    network error, etc.), returns a DummyChatLLM instance that generates template
    responses for debugging and graceful degradation.

    Why async is critical for LLMs:
    1. LLM API calls are extremely I/O-bound (network latency + generation time)
    2. Generation can take 5-30+ seconds for long responses
    3. Without async, one user's query blocks all others
    4. Streaming requires async to yield tokens as they're generated
    5. Enables proper timeout handling and cancellation

    Fallback mode behavior:
    - Returns DummyChatLLM if real model fails to initialize
    - Logs warning about fallback mode activation
    - Generates template responses mentioning unavailability
    - Allows system to continue functioning for debugging

    Args:
        config: LLM configuration specifying provider and parameters.
        fallback_config: Optional fallback configuration for dummy LLM.

    Returns:
        Chat model instance (real or dummy) supporting both sync and async.

    Example:
        >>> llm = create_llm(config.llm, config.fallback)
        >>> # Will use real model if available, dummy if not
        >>> response = await llm.ainvoke(messages)
        >>> # Async streaming
        >>> async for chunk in llm.astream(messages):
        ...     print(chunk.content, end="", flush=True)
    """
    provider = config.provider
    logger.info(f"Creating LLM with provider: {provider}")

    # Determine if fallback is enabled
    use_fallback = fallback_config and fallback_config.enabled if fallback_config else False

    try:
        if provider == "openai":
            api_key = get_api_key(config.openai.api_key_env)
            llm = ChatOpenAI(
                model=config.openai.model,
                temperature=config.openai.temperature,
                max_tokens=config.openai.max_tokens,
                api_key=api_key,
                base_url=config.openai.base_url,
                timeout=config.openai.timeout,
                streaming=config.openai.streaming,
            )
            logger.info(f"Created OpenAI LLM: model={config.openai.model}")
            return llm

        elif provider == "cohere":
            from pydantic import SecretStr

            api_key = get_api_key(config.cohere.api_key_env)
            llm = ChatCohere(
                model=config.cohere.model,
                temperature=config.cohere.temperature,
                cohere_api_key=SecretStr(api_key) if api_key else None,
            )
            logger.info(f"Created Cohere LLM: model={config.cohere.model}")
            return llm

        elif provider == "huggingface":
            api_key = get_api_key(config.huggingface.api_key_env)
            llm = HuggingFaceEndpoint(
                model=config.huggingface.model,
                repo_id=config.huggingface.model,
                temperature=config.huggingface.temperature,
                max_new_tokens=config.huggingface.max_tokens,
                huggingfacehub_api_token=api_key,
            )
            logger.info(f"Created HuggingFace LLM: model={config.huggingface.model}")
            return llm

        elif provider == "custom":
            # Custom OpenAI-compatible endpoint
            api_key = get_api_key(config.custom.api_key_env)
            llm = ChatOpenAI(
                model=config.custom.model,
                temperature=config.custom.temperature,
                max_tokens=config.custom.max_tokens,
                api_key=api_key,
                base_url=config.custom.base_url,
            )
            logger.info(f"Created custom LLM: base_url={config.custom.base_url}")
            return llm

        else:
            raise ValueError(
                f"Unknown LLM provider: {provider}. Supported: openai, cohere, huggingface, custom"
            )

    except Exception as e:
        if use_fallback:
            logger.error(
                f"Failed to create {provider} LLM: {e}. Falling back to DUMMY LLM for debugging."
            )
            return DummyChatLLM()
        else:
            logger.error(f"Failed to create {provider} LLM: {e}")
            raise
