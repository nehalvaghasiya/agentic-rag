"""Minimal validated configuration profile and safe environment overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, Field


class Settings(BaseModel):
    environment: str = "demo"
    store: str = "fake"
    provider: str = "fake"
    model: str = "gpt-4.1-mini"
    embedding_provider: str | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str | None = Field(default=None, repr=False)
    embedding_base_url: str | None = None
    api_key: str | None = Field(default=None, repr=False)
    jwt_secret: str | None = None
    jwt_issuer: str = "agentic-rag"
    jwt_audience: str = "agentic-rag-api"
    base_url: str = "https://api.openai.com/v1"
    database_url: str | None = Field(default=None, repr=False)
    database_admin_url: str | None = Field(default=None, repr=False)
    worker_tenant_id: str = "demo-tenant"
    streaming: bool = True
    sql_dataset_path: str | None = None
    allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    @classmethod
    def load(cls, filename: Path | None = None, env_file: Path | None = Path(".env")) -> Settings:
        values: dict[str, Any] = {}
        if filename is not None:
            values = yaml.safe_load(filename.read_text(encoding="utf-8")) or {}
            if not isinstance(values, dict):
                raise ValueError("Configuration must be a YAML map")
        aliases = {
            "provider": ("LLM_PROVIDER",),
            "model": ("LLM_MODEL",),
            "base_url": ("LLM_BASE_URL",),
            "api_key": ("LLM_API_KEY", "OPENAI_API_KEY"),
            "embedding_provider": ("EMBEDDING_PROVIDER",),
            "embedding_model": ("EMBEDDING_MODEL",),
            "embedding_api_key": ("EMBEDDING_API_KEY",),
            "embedding_base_url": ("EMBEDDING_BASE_URL",),
        }
        file_values = dotenv_values(env_file) if env_file is not None else {}
        for source in (file_values, os.environ):
            for field in cls.model_fields:
                for name in ("AGENTIC_RAG_" + field.upper(), *aliases.get(field, ())):
                    value = source.get(name)
                    if value is not None:
                        values[field] = value
                        break
        return cls.model_validate(values)

    def validate_runtime(self) -> None:
        if self.environment not in {"demo", "local", "production"}:
            raise ValueError("Unsupported environment")
        if self.provider not in {"fake", "openai", "openai_compatible"}:
            raise ValueError("Unsupported provider")
        if self.embedding_provider not in {None, "fake", "openai", "openai_compatible"}:
            raise ValueError("Unsupported embedding provider")
        if self.environment == "production":
            if self.store != "postgres" or not self.database_url:
                raise ValueError("Production requires PostgreSQL-backed persistence")
            if self.provider == "fake" or not self.api_key:
                raise ValueError("Production requires a real model provider")
            if not self.jwt_secret or len(self.jwt_secret) < 32:
                raise ValueError("Production requires verified identity configuration")
            if any(origin == "*" for origin in self.allow_origins):
                raise ValueError("Wildcard CORS prohibited in production")
        if self.store not in {"fake", "postgres"}:
            raise ValueError("Unknown store")
        if self.store == "postgres" and not self.database_url:
            raise ValueError(
                "PostgreSQL requires AGENTIC_RAG_DATABASE_URL; run npm run dev for local setup"
            )

    def public(self) -> dict[str, object]:
        return {
            "environment": self.environment,
            "provider": self.provider,
            "model": self.model,
            "modes": ["auto", "direct", "baseline", "advanced", "agentic"],
            "store": self.store,
            "ephemeral": self.store == "fake",
            "embedding_model": "demo-token-hash-256"
            if (self.embedding_provider or self.provider) == "fake"
            else self.embedding_model,
            "embedding_provider": self.embedding_provider or self.provider,
            "contract_version": "chat-v1",
            "knowledge_management_version": 1,
            "models": [
                {
                    "id": "default",
                    "name": self.model,
                    "streaming": self.streaming,
                    "tools": True,
                    "demo": self.provider == "fake",
                }
            ],
        }
