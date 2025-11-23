"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "RAG Service"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1

    # Security
    rag_service_token: Optional[str] = None
    api_key_header: str = "X-API-Key"

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536
    openai_max_tokens: int = 1024
    openai_temperature: float = 0.7

    # Qdrant
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection: str = "default"
    qdrant_batch_size: int = 100

    # Redis
    redis_url: str = "redis://redis:6379"
    redis_password: Optional[str] = None
    redis_db: int = 0
    redis_cache_ttl: int = 3600  # 1 hour

    # RabbitMQ
    rabbitmq_url: str = "amqp://rabbitmq:5672"
    rabbitmq_user: str = "rabbitmq"
    rabbitmq_password: Optional[str] = None
    rabbitmq_queue: str = "document_processing"

    # MinIO
    minio_url: str = "http://minio:9000"
    minio_access_key: Optional[str] = None
    minio_secret_key: Optional[str] = None
    minio_bucket: str = "documents"

    # RAG Settings
    default_collection: str = "default"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k: int = 5
    similarity_threshold: float = 0.7

    @property
    def redis_connection_url(self) -> str:
        """Build Redis connection URL with password if provided."""
        if self.redis_password:
            # Parse and inject password
            if "://" in self.redis_url:
                protocol, rest = self.redis_url.split("://", 1)
                return f"{protocol}://:{self.redis_password}@{rest}"
        return self.redis_url

    @property
    def rabbitmq_connection_url(self) -> str:
        """Build RabbitMQ connection URL with credentials."""
        if self.rabbitmq_password:
            if "://" in self.rabbitmq_url:
                protocol, rest = self.rabbitmq_url.split("://", 1)
                return f"{protocol}://{self.rabbitmq_user}:{self.rabbitmq_password}@{rest}"
        return self.rabbitmq_url


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
