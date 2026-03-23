from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Gamuda Take Home Backend"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/gamuda"
    storage_dir: Path = Field(default=Path("storage/uploads"))
    artifacts_dir: Path = Field(default=Path("storage/artifacts"))
    jina_api_key: SecretStr | None = None
    jina_embedding_model: str = "jina-embeddings-v5-text-small"
    jina_embedding_base_url: str = "https://api.jina.ai/v1/embeddings"
    jina_embedding_dimensions: int = 1024
    jina_embedding_batch_size: int = 32
    jina_embedding_timeout_seconds: float = 30.0
    pdf_do_table_structure: bool = True
    pdf_table_mode: str = "accurate"
    pdf_num_threads: int = 4
    pdf_layout_batch_size: int = 4
    pdf_table_batch_size: int = 4
    pdf_document_timeout_seconds: int = 120
    groq_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    router_provider: str = "groq"
    router_model: str = "openai/gpt-oss-120b"
    document_agent_provider: str = "groq"
    document_agent_model: str = "openai/gpt-oss-120b"
    data_agent_provider: str = "groq"
    data_agent_model: str = "openai/gpt-oss-120b"
    reporter_provider: str = "groq"
    reporter_model: str = "openai/gpt-oss-20b"
    agent_log_path: Path = Field(default=Path("storage/logs/agent_calls.jsonl"))
    agent_log_include_content: bool = True
    llm_pricing_file: Path = Field(default=Path("app/ai/llm_pricing.yaml"))
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str | None = None

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        normalized = str(value).strip()
        if normalized.startswith("postgres://"):
            return normalized.replace("postgres://", "postgresql+psycopg://", 1)
        if normalized.startswith("postgresql://"):
            return normalized.replace("postgresql://", "postgresql+psycopg://", 1)
        if normalized.startswith("postgresql+psycopg2://"):
            return normalized.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
        return normalized

    @field_validator("pdf_table_mode", mode="before")
    @classmethod
    def normalize_pdf_table_mode(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if normalized not in {"fast", "accurate"}:
            raise ValueError("pdf_table_mode must be either 'fast' or 'accurate'.")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()
