"""
Configuration module for Agentic RAG.

Loads and validates all configuration from config.yaml using Pydantic models.
Provides type-safe access to all application settings.

This module follows the Single Responsibility Principle by focusing solely on
configuration loading and validation.
"""

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class AppConfig(BaseModel):
    """Application-level configuration."""

    name: str = "Agentic RAG"
    version: str = "1.0.0"
    debug: bool = False
    max_upload_size_mb: int = Field(default=5, gt=0)


class FallbackConfig(BaseModel):
    """Fallback mode configuration for graceful degradation."""

    enabled: bool = True
    embedding_dimensions: int = Field(default=1536, gt=0)
    notify_user: bool = True


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_file: str = "logs/app.log"
    rotation: str = "10 MB"
    retention: str = "7 days"
    format: str


class PDFLoaderConfig(BaseModel):
    """PDF document loader configuration."""

    enabled: bool = True
    extract_images: bool = True


class DOCXLoaderConfig(BaseModel):
    """DOCX document loader configuration."""

    enabled: bool = True


class WebsiteLoaderConfig(BaseModel):
    """Website loader configuration."""

    enabled: bool = True
    timeout_seconds: int = Field(default=30, gt=0)
    user_agent: str
    max_pages: int = Field(default=10, gt=0)


class ImageLoaderConfig(BaseModel):
    """Image loader configuration."""

    enabled: bool = True
    ocr_enabled: bool = True
    supported_formats: list[str]


class TextLoaderConfig(BaseModel):
    """Text file loader configuration."""

    enabled: bool = True
    supported_extensions: list[str]


class LoadersConfig(BaseModel):
    """All document loaders configuration."""

    pdf: PDFLoaderConfig
    docx: DOCXLoaderConfig
    text: TextLoaderConfig
    website: WebsiteLoaderConfig
    image: ImageLoaderConfig


class CleaningConfig(BaseModel):
    """Text cleaning configuration."""

    remove_extra_whitespace: bool = True
    remove_special_chars: bool = False
    lowercase: bool = False


class SummarizationConfig(BaseModel):
    """Summarization preprocessing configuration."""

    enabled: bool = False
    model_provider: str = "openai"
    max_chunk_length: int = Field(default=2000, gt=0)


class PreprocessingConfig(BaseModel):
    """Preprocessing pipeline configuration."""

    enabled: bool = True
    cleaning: CleaningConfig
    summarization: SummarizationConfig


class RecursiveSplitterConfig(BaseModel):
    """Recursive character text splitter configuration."""

    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=200, ge=0)
    separators: list[str]


class CharacterSplitterConfig(BaseModel):
    """Character text splitter configuration."""

    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=200, ge=0)
    separator: str = "\n"


class TokenSplitterConfig(BaseModel):
    """Token-based text splitter configuration."""

    chunk_size: int = Field(default=512, gt=0)
    chunk_overlap: int = Field(default=50, ge=0)
    encoding_name: str = "cl100k_base"


class SemanticSplitterConfig(BaseModel):
    """Semantic text splitter configuration."""

    buffer_size: int = Field(default=1, ge=0)
    breakpoint_threshold_type: Literal["percentile", "standard_deviation", "interquartile"]


class SplittingConfig(BaseModel):
    """Text splitting configuration."""

    strategy: Literal["recursive", "character", "token", "semantic"] = "recursive"
    recursive: RecursiveSplitterConfig
    character: CharacterSplitterConfig
    token: TokenSplitterConfig
    semantic: SemanticSplitterConfig


class OpenAIEmbeddingConfig(BaseModel):
    """OpenAI embeddings configuration."""

    model: str = "text-embedding-3-small"
    dimensions: int = Field(default=1536, gt=0)
    api_key_env: str
    base_url: str | None = None
    timeout: int = Field(default=60, gt=0)
    max_retries: int = Field(default=3, ge=0)


class HuggingFaceEmbeddingConfig(BaseModel):
    """HuggingFace embeddings configuration."""

    model: str
    device: Literal["cpu", "cuda", "mps"] = "cpu"
    normalize_embeddings: bool = True


class CohereEmbeddingConfig(BaseModel):
    """Cohere embeddings configuration."""

    model: str = "embed-english-v3.0"
    input_type: str = "search_document"
    api_key_env: str


class CustomEmbeddingConfig(BaseModel):
    """Custom OpenAI-compatible embeddings configuration."""

    base_url: str
    model: str
    api_key_env: str
    dimensions: int = Field(default=768, gt=0)


class EmbeddingsConfig(BaseModel):
    """Embeddings configuration."""

    provider: Literal["openai", "huggingface", "cohere", "custom"] = "openai"
    openai: OpenAIEmbeddingConfig
    huggingface: HuggingFaceEmbeddingConfig
    cohere: CohereEmbeddingConfig
    custom: CustomEmbeddingConfig


class PGVectorConfig(BaseModel):
    """PGVector database configuration."""

    host: str = "localhost"
    port: int = Field(default=5432, gt=0, le=65535)
    database: str
    user: str
    password_env: str
    collection_name: str = "documents"
    use_async: bool = True
    pool_size: int = Field(default=10, gt=0)
    max_overflow: int = Field(default=20, ge=0)


class VectorStoreConfig(BaseModel):
    """Vector store configuration."""

    provider: Literal["pgvector"] = "pgvector"
    pgvector: PGVectorConfig


class MMRConfig(BaseModel):
    """Maximum Marginal Relevance configuration."""

    fetch_k: int = Field(default=20, gt=0)
    lambda_mult: float = Field(default=0.5, ge=0, le=1)


class RerankingConfig(BaseModel):
    """Reranking configuration."""

    enabled: bool = False
    provider: Literal["cohere", "custom"] = "cohere"
    model: str = "rerank-english-v3.0"
    top_n: int = Field(default=3, gt=0)


class RetrievalConfig(BaseModel):
    """Retrieval configuration."""

    strategy: Literal["similarity", "mmr", "similarity_score_threshold"] = "similarity"
    top_k: int = Field(default=5, gt=0)
    mmr: MMRConfig
    score_threshold: float = Field(default=0.7, ge=0, le=1)
    reranking: RerankingConfig


class OpenAILLMConfig(BaseModel):
    """OpenAI LLM configuration."""

    model: str = "gpt-4o-mini"
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2000, gt=0)
    api_key_env: str
    base_url: str | None = None
    timeout: int = Field(default=120, gt=0)
    streaming: bool = True


class CohereLLMConfig(BaseModel):
    """Cohere LLM configuration."""

    model: str = "command-r-plus"
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2000, gt=0)
    api_key_env: str


class HuggingFaceLLMConfig(BaseModel):
    """HuggingFace LLM configuration."""

    model: str
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2000, gt=0)
    api_key_env: str


class CustomLLMConfig(BaseModel):
    """Custom OpenAI-compatible LLM configuration."""

    base_url: str
    model: str
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2000, gt=0)
    api_key_env: str


class LLMConfig(BaseModel):
    """LLM configuration."""

    provider: Literal["openai", "cohere", "huggingface", "custom"] = "openai"
    openai: OpenAILLMConfig
    cohere: CohereLLMConfig
    huggingface: HuggingFaceLLMConfig
    custom: CustomLLMConfig


class RetrieverToolConfig(BaseModel):
    """Retriever tool configuration."""

    enabled: bool = True
    description: str


class WebSearchToolConfig(BaseModel):
    """Web search tool configuration."""

    enabled: bool = True
    provider: Literal["duckduckgo", "serp", "custom"] = "duckduckgo"
    max_results: int = Field(default=5, gt=0)
    serp_api_key_env: str | None = None


class CalculatorToolConfig(BaseModel):
    """Calculator tool configuration."""

    enabled: bool = True
    description: str


class QueryOptimizerToolConfig(BaseModel):
    """Query optimizer tool configuration."""

    enabled: bool = True
    description: str


class RelevancyCheckerToolConfig(BaseModel):
    """Relevancy checker tool configuration."""

    enabled: bool = True
    threshold: float = Field(default=0.6, ge=0, le=1)
    description: str


class AgentToolsConfig(BaseModel):
    """All agent tools configuration."""

    retriever: RetrieverToolConfig
    web_search: WebSearchToolConfig
    calculator: CalculatorToolConfig
    query_optimizer: QueryOptimizerToolConfig
    relevancy_checker: RelevancyCheckerToolConfig


class AgentsConfig(BaseModel):
    """Agents configuration."""

    enabled: bool = True
    max_iterations: int = Field(default=10, gt=0)
    tools: AgentToolsConfig


class GenerationConfig(BaseModel):
    """Answer generation configuration."""

    use_chat_history: bool = True
    max_history_messages: int = Field(default=10, gt=0)
    include_sources: bool = True


class PromptsConfig(BaseModel):
    """RAG prompts configuration."""

    system: str
    qa_template: str
    condense_question_template: str


class RAGConfig(BaseModel):
    """RAG pipeline configuration."""

    generation: GenerationConfig
    prompts: PromptsConfig


class APIConfig(BaseModel):
    """API server configuration."""

    host: str = "0.0.0.0"
    port: int = Field(default=8000, gt=0, le=65535)
    reload: bool = False
    workers: int = Field(default=4, gt=0)
    cors_origins: list[str]
    cors_methods: list[str]
    cors_headers: list[str]


class ChatConfig(BaseModel):
    """Chat UI configuration."""

    placeholder: str
    examples: list[str]


class FrontendConfig(BaseModel):
    """Frontend configuration."""

    host: str = "0.0.0.0"
    port: int = Field(default=7860, gt=0, le=65535)
    share: bool = False
    theme: str = "default"
    title: str
    description: str
    chat: ChatConfig


class Config(BaseSettings):
    """
    Main configuration class for Agentic RAG.

    Loads configuration from config.yaml and validates all settings using Pydantic.
    All nested configuration objects are strongly typed for IDE support and
    runtime validation.

    Example:
        >>> config = load_config()
        >>> print(config.llm.provider)
        'openai'
        >>> print(config.embeddings.openai.model)
        'text-embedding-3-small'
    """

    app: AppConfig
    fallback: FallbackConfig
    logging: LoggingConfig
    loaders: LoadersConfig
    preprocessing: PreprocessingConfig
    splitting: SplittingConfig
    embeddings: EmbeddingsConfig
    vectorstore: VectorStoreConfig
    retrieval: RetrievalConfig
    llm: LLMConfig
    agents: AgentsConfig
    rag: RAGConfig
    api: APIConfig
    frontend: FrontendConfig

    class Config:
        """Pydantic configuration."""

        extra = "forbid"  # Disallow unknown fields


def load_config(config_path: str | Path = "config.yaml") -> Config:
    """
    Load and validate configuration from YAML file.

    This function reads the configuration file, parses the YAML, and validates
    all settings against the Pydantic models. It will raise ValidationError if
    any configuration values are invalid or missing.

    Args:
        config_path: Path to the configuration YAML file. Defaults to config.yaml
                    in the current working directory.

    Returns:
        Validated Config object with all settings loaded and type-checked.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        yaml.YAMLError: If the YAML file is malformed.
        pydantic.ValidationError: If any configuration values are invalid.

    Example:
        >>> config = load_config("config.yaml")
        >>> # Configuration is now validated and ready to use
        >>> api_key = os.getenv(config.llm.openai.api_key_env)
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        config_dict = yaml.safe_load(f)

    return Config(**config_dict)


def get_api_key(env_var_name: str) -> str:
    """
    Retrieve API key from environment variable.

    This helper function fetches API keys from environment variables and provides
    clear error messages if they are not set. All secrets should be stored in
    environment variables, never in config.yaml.

    Args:
        env_var_name: Name of the environment variable containing the API key.

    Returns:
        The API key value from the environment variable.

    Raises:
        ValueError: If the environment variable is not set or is empty.

    Example:
        >>> api_key = get_api_key("OPENAI_API_KEY")
        >>> # Use api_key for authentication
    """
    api_key = os.getenv(env_var_name)
    if not api_key:
        raise ValueError(
            f"API key environment variable '{env_var_name}' is not set. "
            f"Please set it in your environment or .env file."
        )
    return api_key
