from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Gamuda Take Home Backend"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/gamuda"
    storage_dir: Path = Field(default=Path("storage/uploads"))
    artifacts_dir: Path = Field(default=Path("storage/artifacts"))
    jina_api_key: SecretStr | None = None
    jina_embedding_model: str = "jina-embeddings-v5-text-small"
    jina_embedding_base_url: str = "https://api.jina.ai/v1/embeddings"
    jina_embedding_dimensions: int = 1024
    jina_embedding_batch_size: int = 32
    jina_embedding_timeout_seconds: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
