"""Configuration and prompts.

All application settings and prompt templates in one place.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    data_dir: Path = Field(default=Path(".data"), description="Root directory for data storage")

    # Chunking
    chunk_size: int = Field(default=800, description="Maximum chunk size in characters")
    chunk_overlap: int = Field(default=120, description="Overlap between chunks")

    # Retrieval
    top_k: int = Field(default=5, description="Number of documents to retrieve")
    max_retries: int = Field(default=2, description="Max retries for query refinement")

    # LLM
    openai_api_key: SecretStr | None = Field(default=None, description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model name")
    openai_base_url: str | None = Field(default=None, description="Custom OpenAI base URL")

    # Embeddings
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Default embedding model",
    )

    # Mode
    mode: Literal["production", "deterministic"] = Field(
        default="production",
        description="Run mode: 'deterministic' uses hash embeddings for testing",
    )

    # Server
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        description="Allowed CORS origins",
    )
    upload_dir: Path = Field(
        default=Path(".data/uploads"),
        description="Directory for uploaded files",
    )


class Prompts:
    """Prompt templates for the RAG workflow."""

    QUERY_REWRITE: str = (
        "Rewrite the following question as a concise search query. "
        "Output only the query, nothing else.\n\n"
        "Question: {question}"
    )

    GRADE: str = (
        "Is this document excerpt relevant to answering the question? "
        "Answer with only 'yes' or 'no'.\n\n"
        "Question: {question}\n\n"
        "Excerpt: {excerpt}"
    )

    ANSWER: str = (
        "Answer the question using only the provided context. "
        "If the context doesn't contain the answer, say so. "
        "Cite sources using [1], [2], etc.\n\n"
        "Question: {question}\n\n"
        "Context:\n{context}"
    )


# Singleton settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the application settings (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings (for testing)."""
    global _settings
    _settings = None


__all__ = ["Settings", "Prompts", "get_settings", "reset_settings"]
