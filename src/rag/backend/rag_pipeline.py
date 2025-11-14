"""
rag_pipeline.py: RAG retrieval and generation pipeline.

Orchestrates the complete RAG workflow: retrieval, reranking, and generation.
Includes fallback mode tracking for graceful degradation.
"""

from typing import Any

from langchain.memory import ConversationBufferMemory
from langchain_core.documents import Document
from loguru import logger

from rag.backend.embeddings.dummy_embeddings import DummyEmbeddings
from rag.backend.llm.dummy_llm import DummyChatLLM
from rag.config import Config


class RAGPipeline:
    """
    Complete RAG pipeline with retrieval and generation.

    This class orchestrates the full RAG workflow:
    1. Query understanding and reformulation
    2. Document retrieval from vector store
    3. Optional reranking
    4. Context-aware answer generation
    5. Source citation

    All API calls (LLM, embeddings, DB) are async to prevent blocking.

    Includes fallback mode detection: Tracks when dummy models are being used
    and returns warnings to inform users.

    Attributes:
        config: RAG configuration.
        vectorstore: Vector store for retrieval.
        llm: Language model for generation.
        memory: Conversation memory for chat history.
        warnings: List of active warnings (e.g., fallback mode).
    """

    def __init__(self, config: Config, vectorstore: Any, llm: Any, embeddings: Any = None) -> None:
        """
        Initialize RAG pipeline.

        Args:
            config: Application configuration.
            vectorstore: Async vector store instance.
            llm: Language model instance.
            embeddings: Optional embeddings instance for fallback detection.
        """
        self.config = config
        self.vectorstore = vectorstore
        self.llm = llm
        self.embeddings = embeddings
        self.warnings: list[str] = []

        # Detect fallback mode
        self._detect_fallback_mode()

        # Initialize conversation memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="answer",
        )

        logger.info(
            f"RAG pipeline initialized. "
            f"Fallback mode: {bool(self.warnings)}, Warnings: {self.warnings}"
        )

    def _detect_fallback_mode(self) -> None:
        """
        Detect if system is running in fallback mode.

        Checks if dummy models are being used and populates warnings list.
        This information is included in API responses to notify users.
        """
        # Check if using dummy embeddings
        if self.embeddings and isinstance(self.embeddings, DummyEmbeddings):
            warning = (
                "⚠️ Embedding model unavailable - using dummy embeddings for debugging. "
                "Retrieval may not be accurate."
            )
            self.warnings.append(warning)
            logger.warning(warning)

        # Check if using dummy LLM
        if isinstance(self.llm, DummyChatLLM):
            warning = (
                "⚠️ Language model unavailable - using dummy responses for debugging. "
                "Answers are template-based, not AI-generated."
            )
            self.warnings.append(warning)
            logger.warning(warning)

        if self.warnings and self.config.fallback.notify_user:
            logger.info(
                f"Fallback mode active with {len(self.warnings)} warnings. "
                "System will continue functioning with reduced capabilities."
            )

    def get_warnings(self) -> list[str]:
        """
        Get list of active warnings.

        Returns:
            List of warning messages for user notification.
        """
        return self.warnings.copy()

    async def retrieve_documents(self, query: str, k: int | None = None) -> list[Document]:
        """
        Retrieve relevant documents for a query.

        This is async because:
        1. Query embedding uses API (async I/O)
        2. Vector DB search is I/O-bound
        3. Multiple concurrent retrievals should not block each other

        Args:
            query: User query.
            k: Number of documents to retrieve (defaults to config).

        Returns:
            List of relevant documents.

        Example:
            >>> pipeline = RAGPipeline(config, vectorstore, llm)
            >>> docs = await pipeline.retrieve_documents("What is RAG?")
        """
        k = k or self.config.retrieval.top_k
        strategy = self.config.retrieval.strategy

        logger.info(f"Retrieving documents: strategy={strategy}, k={k}")

        try:
            if strategy == "similarity":
                documents = await self.vectorstore.similarity_search(query, k=k)

            elif strategy == "mmr":
                documents = await self.vectorstore.max_marginal_relevance_search(
                    query,
                    k=k,
                    fetch_k=self.config.retrieval.mmr.fetch_k,
                    lambda_mult=self.config.retrieval.mmr.lambda_mult,
                )

            elif strategy == "similarity_score_threshold":
                results = await self.vectorstore.similarity_search_with_score(query, k=k)
                # Filter by score threshold
                documents = [
                    doc for doc, score in results if score >= self.config.retrieval.score_threshold
                ]

            else:
                raise ValueError(f"Unknown retrieval strategy: {strategy}")

            logger.info(f"Retrieved {len(documents)} documents")
            return documents

        except Exception as e:
            logger.exception(f"Error retrieving documents: {e}")
            raise

    async def generate_answer(
        self, query: str, context_documents: list[Document]
    ) -> dict[str, Any]:
        """
        Generate an answer using retrieved context.

        This is async because:
        1. LLM API calls can take 5-30+ seconds
        2. Streaming generation yields tokens asynchronously
        3. Multiple users should be served concurrently

        Args:
            query: User query.
            context_documents: Retrieved context documents.

        Returns:
            Dictionary with answer and metadata (sources, etc.).

        Example:
            >>> docs = await pipeline.retrieve_documents("What is RAG?")
            >>> result = await pipeline.generate_answer("What is RAG?", docs)
            >>> print(result["answer"])
        """
        logger.info(f"Generating answer for query: {query[:100]}...")

        try:
            # Format context
            context = "\n\n".join(
                [
                    f"Document {i + 1}:\n{doc.page_content}"
                    for i, doc in enumerate(context_documents)
                ]
            )

            # Get chat history
            chat_history = self.memory.load_memory_variables({}).get("chat_history", [])
            chat_history_str = "\n".join([f"{msg.type}: {msg.content}" for msg in chat_history])

            # Format prompt
            prompt_template = self.config.rag.prompts.qa_template
            prompt = prompt_template.format(
                context=context, chat_history=chat_history_str, question=query
            )

            # Generate answer (async for API-based LLM)
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=self.config.rag.prompts.system),
                HumanMessage(content=prompt),
            ]

            response = await self.llm.ainvoke(messages)
            answer = response.content

            # Save to memory
            self.memory.save_context({"input": query}, {"answer": answer})

            # Prepare result
            result = {
                "answer": answer,
                "query": query,
                "context_documents": context_documents,
            }

            if self.config.rag.generation.include_sources:
                result["sources"] = [
                    {
                        "content": doc.page_content[:200] + "...",
                        "metadata": doc.metadata,
                    }
                    for doc in context_documents
                ]

            logger.info(f"Generated answer ({len(answer)} chars)")
            return result

        except Exception as e:
            logger.exception(f"Error generating answer: {e}")
            raise

    async def query(self, user_query: str) -> dict[str, Any]:
        """
        Complete RAG query: retrieve and generate.

        This is the main entry point for RAG queries. Async to handle all
        I/O operations (embedding, DB, LLM) without blocking.

        Args:
            user_query: User's question.

        Returns:
            Complete result with answer and sources.

        Example:
            >>> pipeline = RAGPipeline(config, vectorstore, llm)
            >>> result = await pipeline.query("What is RAG?")
            >>> print(result["answer"])
            >>> for source in result["sources"]:
            ...     print(source["metadata"])
        """
        logger.info(f"Processing RAG query: {user_query[:100]}...")

        try:
            # Step 1: Retrieve documents
            documents = await self.retrieve_documents(user_query)

            if not documents:
                logger.warning("No documents retrieved")
                return {
                    "answer": "I don't have enough information to answer that question.",
                    "query": user_query,
                    "context_documents": [],
                    "sources": [],
                }

            # Step 2: Generate answer
            result = await self.generate_answer(user_query, documents)

            logger.info("RAG query completed successfully")
            return result

        except Exception as e:
            logger.exception(f"Error processing RAG query: {e}")
            raise
