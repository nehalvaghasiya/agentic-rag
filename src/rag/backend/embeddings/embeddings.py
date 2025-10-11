"""
Embedding provider implementations with async support.

Supports OpenAI, HuggingFace (local), Cohere, and custom OpenAI-compatible endpoints.
API-based embeddings are async to prevent blocking during network I/O.

Includes fallback mode for graceful degradation when models are unavailable.
"""

from langchain_cohere import CohereEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from loguru import logger

from rag.backend.embeddings.dummy_embeddings import DummyEmbeddings
from rag.config import EmbeddingsConfig, get_api_key


def create_embeddings(config: EmbeddingsConfig, fallback_config=None):
    """
    Factory function to create embeddings based on configuration.

    This function creates the appropriate embeddings model based on the configured
    provider. API-based providers (OpenAI, Cohere, custom) support async operations
    for non-blocking I/O, while local models (HuggingFace) are synchronous.

    Includes fallback mode: If the real embedding model is unavailable (missing API key,
    network error, etc.), returns a DummyEmbeddings instance that generates deterministic
    hash-based embeddings for debugging and graceful degradation.

    Why async for API-based embeddings:
    1. Embedding API calls are network I/O-bound (can take 100ms+ per request)
    2. We often need to embed multiple chunks in parallel
    3. Async allows concurrent embedding generation with asyncio.gather
    4. Prevents blocking the event loop during batch embedding operations

    For local embeddings (HuggingFace):
    - CPU/GPU-bound inference, no network I/O
    - Already optimized for batch processing
    - Async would not provide benefits

    Fallback mode behavior:
    - Returns DummyEmbeddings if real model fails to initialize
    - Logs warning about fallback mode activation
    - Allows system to continue functioning for debugging
    - Useful when API keys are missing or services are down

    Args:
        config: Embeddings configuration specifying provider and parameters.
        fallback_config: Optional fallback configuration for dummy embeddings.

    Returns:
        Embeddings instance (real or dummy) supporting both sync and async methods.

    Example:
        >>> embeddings = create_embeddings(config.embeddings, config.fallback)
        >>> # Will use real model if available, dummy if not
        >>> vectors = await embeddings.aembed_documents(texts)
    """
    provider = config.provider
    logger.info(f"Creating embeddings with provider: {provider}")

    # Determine if fallback is enabled
    use_fallback = fallback_config and fallback_config.enabled if fallback_config else False

    try:
        if provider == "openai":
            from pydantic import SecretStr

            api_key = get_api_key(config.openai.api_key_env)
            embeddings = OpenAIEmbeddings(
                model=config.openai.model,
                dimensions=config.openai.dimensions,
                api_key=SecretStr(api_key) if api_key else None,
                base_url=config.openai.base_url,
                timeout=config.openai.timeout,
                max_retries=config.openai.max_retries,
            )
            logger.info(
                f"Created OpenAI embeddings: model={config.openai.model}, "
                f"dimensions={config.openai.dimensions}"
            )
            return embeddings

        elif provider == "huggingface":
            # Local embeddings - synchronous, no API key needed
            embeddings = HuggingFaceEmbeddings(
                model_name=config.huggingface.model,
                model_kwargs={"device": config.huggingface.device},
                encode_kwargs={"normalize_embeddings": config.huggingface.normalize_embeddings},
            )
            logger.info(
                f"Created HuggingFace embeddings: model={config.huggingface.model}, "
                f"device={config.huggingface.device}"
            )
            return embeddings

        elif provider == "cohere":
            import httpx
            from pydantic import SecretStr

            api_key = get_api_key(config.cohere.api_key_env)
            embeddings = CohereEmbeddings(
                model=config.cohere.model,
                cohere_api_key=SecretStr(api_key) if api_key else None,
                client=httpx.Client(),
                async_client=httpx.AsyncClient(),
            )
            logger.info(f"Created Cohere embeddings: model={config.cohere.model}")
            return embeddings

        elif provider == "custom":
            # Custom OpenAI-compatible endpoint
            from pydantic import SecretStr

            api_key = get_api_key(config.custom.api_key_env)
            embeddings = OpenAIEmbeddings(
                model=config.custom.model,
                api_key=SecretStr(api_key) if api_key else None,
                base_url=config.custom.base_url,
                dimensions=config.custom.dimensions,
            )
            logger.info(
                f"Created custom embeddings: base_url={config.custom.base_url}, "
                f"model={config.custom.model}"
            )
            return embeddings

        else:
            raise ValueError(
                f"Unknown embeddings provider: {provider}. "
                f"Supported: openai, huggingface, cohere, custom"
            )

    except Exception as e:
        if use_fallback:
            logger.error(
                f"Failed to create {provider} embeddings: {e}. "
                f"Falling back to DUMMY embeddings for debugging."
            )
            dimensions = fallback_config.embedding_dimensions if fallback_config else 1536
            return DummyEmbeddings(dimensions=dimensions)
        else:
            logger.error(f"Failed to create {provider} embeddings: {e}")
            raise


async def embed_documents_async(embeddings, documents: list[str]) -> list[list[float]]:
    """
    Embed documents asynchronously using API-based embeddings.

    This function uses async embedding generation for API-based providers.
    For I/O-bound embedding APIs, this allows concurrent processing of multiple
    batches and prevents blocking the event loop.

    Why async is beneficial here:
    1. Embedding APIs have network latency (50-500ms per request)
    2. We can embed multiple chunks concurrently with asyncio.gather
    3. Significantly faster for large document sets
    4. Doesn't block other API requests during embedding generation

    Args:
        embeddings: Embeddings instance (must support async).
        documents: List of text documents to embed.

    Returns:
        List of embedding vectors.

    Example:
        >>> embeddings = create_embeddings(config.embeddings)
        >>> texts = [doc.page_content for doc in chunks]
        >>> vectors = await embed_documents_async(embeddings, texts)
    """
    logger.debug(f"Embedding {len(documents)} documents asynchronously")

    # Check if embeddings support async
    if hasattr(embeddings, "aembed_documents"):
        # Use async method for API-based embeddings
        vectors = await embeddings.aembed_documents(documents)
        logger.debug(f"Generated {len(vectors)} embeddings asynchronously")
        return vectors
    else:
        # Fallback to sync for local embeddings (HuggingFace)
        logger.debug("Using sync embedding (local model)")
        import asyncio

        loop = asyncio.get_event_loop()
        vectors = await loop.run_in_executor(None, embeddings.embed_documents, documents)
        return vectors


async def embed_query_async(embeddings, query: str) -> list[float]:
    """
    Embed a query asynchronously.

    Uses async for API-based embeddings to avoid blocking during query embedding.
    This is critical for user-facing query responses to maintain low latency.

    Args:
        embeddings: Embeddings instance.
        query: Query text to embed.

    Returns:
        Query embedding vector.

    Example:
        >>> embeddings = create_embeddings(config.embeddings)
        >>> query_vector = await embed_query_async(embeddings, "What is RAG?")
    """
    logger.debug(f"Embedding query: {query[:50]}...")

    if hasattr(embeddings, "aembed_query"):
        vector = await embeddings.aembed_query(query)
        logger.debug("Generated query embedding asynchronously")
        return vector
    else:
        # Fallback to sync
        import asyncio

        loop = asyncio.get_event_loop()
        vector = await loop.run_in_executor(None, embeddings.embed_query, query)
        return vector
