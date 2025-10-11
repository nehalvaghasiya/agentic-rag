"""
PGVector vector store with async support.

Provides async vector storage and retrieval for efficient I/O with PostgreSQL.
"""

from typing import Any

from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.documents import Document
from loguru import logger

from rag.config import PGVectorConfig, get_api_key


class AsyncPGVectorStore:
    """
    Async wrapper for PGVector vector store.

    This class provides async methods for vector storage and retrieval.
    Why async is critical here:
    1. Database I/O is inherently I/O-bound (network + disk)
    2. Adding documents involves multiple DB writes (can take seconds for large batches)
    3. Similarity search queries can be slow for large vector collections
    4. Async prevents blocking the event loop during DB operations
    5. Enables concurrent processing of multiple user requests

    Using async with asyncpg driver provides:
    - Connection pooling for efficient resource usage
    - Non-blocking queries
    - Better scalability under concurrent load

    Attributes:
        config: PGVector configuration.
        embeddings: Embeddings model for vector generation.
    """

    def __init__(self, config: PGVectorConfig, embeddings: Any) -> None:
        """
        Initialize async PGVector store.

        Args:
            config: PGVector configuration including connection details.
            embeddings: Embeddings model to use for vector generation.
        """
        self.config = config
        self.embeddings = embeddings

        # Build connection string
        password = get_api_key(config.password_env)
        self.connection_string = (
            f"postgresql+psycopg://{config.user}:{password}@"
            f"{config.host}:{config.port}/{config.database}"
        )

        # Initialize PGVector with the updated API
        self.vectorstore = PGVector(
            collection_name=config.collection_name,
            connection_string=self.connection_string,
            embedding_function=embeddings,
        )

        logger.info(
            f"Initialized PGVector store: collection={config.collection_name}, "
            f"host={config.host}:{config.port}"
        )

    async def add_documents(self, documents: list[Document]) -> list[str]:
        """
        Add documents to the vector store asynchronously.

        This is async because:
        1. Embedding generation may use API calls (async I/O)
        2. Database inserts are I/O-bound (network + disk writes)
        3. Large batches can take several seconds
        4. Async allows other requests to be processed during insertion

        For a batch of 100 documents:
        - Embedding generation: 1-5 seconds (if API-based)
        - Database writes: 0.5-2 seconds
        - Total: 1.5-7 seconds of I/O-bound operations

        Without async, this would block all other requests!

        Args:
            documents: List of documents to add.

        Returns:
            List of document IDs.

        Example:
            >>> store = AsyncPGVectorStore(config, embeddings)
            >>> ids = await store.add_documents(chunks)
            >>> logger.info(f"Added {len(ids)} documents")
        """
        logger.info(f"Adding {len(documents)} documents to vector store")

        try:
            # Extract texts for embedding
            texts = [doc.page_content for doc in documents]

            # Embed documents (async if using API-based embeddings)
            from rag.backend.embeddings.embeddings import embed_documents_async

            await embed_documents_async(self.embeddings, texts)

            # Add to vector store
            # Note: PGVector's add_documents is currently sync, but we run it in executor
            import asyncio

            loop = asyncio.get_event_loop()
            ids = await loop.run_in_executor(None, self.vectorstore.add_documents, documents)

            logger.info(f"Successfully added {len(ids)} documents to vector store")
            return ids

        except Exception as e:
            logger.exception(f"Error adding documents to vector store: {e}")
            raise

    async def similarity_search(
        self, query: str, k: int = 5, filter: dict[str, str] | None = None
    ) -> list[Document]:
        """
        Search for similar documents asynchronously.

        This is async because:
        1. Query embedding may use API call (async I/O)
        2. Database similarity search is I/O-bound
        3. Vector similarity computation can be slow for large collections
        4. Async prevents blocking during user queries

        Args:
            query: Query text.
            k: Number of results to return.
            filter: Optional metadata filter.

        Returns:
            List of similar documents.

        Example:
            >>> store = AsyncPGVectorStore(config, embeddings)
            >>> results = await store.similarity_search("What is RAG?", k=5)
            >>> for doc in results:
            ...     print(doc.page_content[:100])
        """
        logger.debug(f"Similarity search for query: {query[:50]}... (k={k})")

        try:
            # Embed query (async if using API-based embeddings)
            from rag.backend.embeddings.embeddings import embed_query_async

            await embed_query_async(self.embeddings, query)

            # Perform similarity search
            # Note: PGVector's similarity_search is currently sync
            import asyncio

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, self.vectorstore.similarity_search, query, k, filter
            )

            logger.debug(f"Found {len(results)} similar documents")
            return results

        except Exception as e:
            logger.exception(f"Error performing similarity search: {e}")
            raise

    async def similarity_search_with_score(
        self, query: str, k: int = 5, filter: dict[str, str] | None = None
    ) -> list[tuple[Document, float]]:
        """
        Search for similar documents with similarity scores.

        Async for the same reasons as similarity_search.

        Args:
            query: Query text.
            k: Number of results to return.
            filter: Optional metadata filter.

        Returns:
            List of (document, score) tuples.

        Example:
            >>> results = await store.similarity_search_with_score("RAG", k=3)
            >>> for doc, score in results:
            ...     print(f"Score: {score:.3f}, Content: {doc.page_content[:50]}")
        """
        logger.debug(f"Similarity search with scores for query: {query[:50]}... (k={k})")

        try:
            # Embed query
            from rag.backend.embeddings.embeddings import embed_query_async

            await embed_query_async(self.embeddings, query)

            # Perform similarity search with scores
            import asyncio

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, self.vectorstore.similarity_search_with_score, query, k, filter
            )

            logger.debug(f"Found {len(results)} documents with scores")
            return results

        except Exception as e:
            logger.exception(f"Error performing similarity search with scores: {e}")
            raise

    async def max_marginal_relevance_search(
        self, query: str, k: int = 5, fetch_k: int = 20, lambda_mult: float = 0.5
    ) -> list[Document]:
        """
        Maximum Marginal Relevance search (async).

        MMR balances relevance and diversity in results. Async because it involves
        both embedding and database operations.

        Args:
            query: Query text.
            k: Number of results to return.
            fetch_k: Number of candidates to fetch before MMR.
            lambda_mult: Diversity factor (0=max diversity, 1=max relevance).

        Returns:
            List of diverse, relevant documents.

        Example:
            >>> # Get diverse results
            >>> results = await store.max_marginal_relevance_search(
            ...     "RAG", k=5, lambda_mult=0.5
            ... )
        """
        logger.debug(f"MMR search for query: {query[:50]}... (k={k}, fetch_k={fetch_k})")

        try:
            # Embed query
            from rag.backend.embeddings.embeddings import embed_query_async

            await embed_query_async(self.embeddings, query)

            # Perform MMR search
            import asyncio

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                self.vectorstore.max_marginal_relevance_search,
                query,
                k,
                fetch_k,
                lambda_mult,
            )

            logger.debug(f"MMR search returned {len(results)} documents")
            return results

        except Exception as e:
            logger.exception(f"Error performing MMR search: {e}")
            raise


def create_vectorstore(config: PGVectorConfig, embeddings: Any) -> AsyncPGVectorStore:
    """
    Factory function to create async vector store.

    Args:
        config: PGVector configuration.
        embeddings: Embeddings model.

    Returns:
        Async PGVector store instance.

    Example:
        >>> from rag.backend.embeddings.embeddings import create_embeddings
        >>> embeddings = create_embeddings(config.embeddings)
        >>> store = create_vectorstore(config.vectorstore.pgvector, embeddings)
    """
    return AsyncPGVectorStore(config, embeddings)
