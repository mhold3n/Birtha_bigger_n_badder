"""Configuration management using Pydantic Settings."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenAI/Worker configuration
    openai_base_url: str = Field(
        default="http://worker.local:8000/v1",
        description="Base URL for OpenAI-compatible API (vLLM/TGI)",
    )
    openai_api_key: str = Field(
        default="local-dev-token",
        description="API key for worker authentication",
    )

    # Redis configuration
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL",
    )

    # Application settings
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    host: str = Field(default="0.0.0.0", description="Host to bind to")
    port: int = Field(default=8080, description="Port to bind to")

    # Security
    jwt_secret: Optional[str] = Field(default=None, description="JWT secret key")
    encryption_key: Optional[str] = Field(default=None, description="Encryption key")

    # Metrics
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")

    def model_post_init(self, __context) -> None:
        """Validate configuration after initialization."""
        if self.debug and not self.jwt_secret:
            self.jwt_secret = "dev-secret-key"
        if self.debug and not self.encryption_key:
            self.encryption_key = "dev-encryption-key-32-chars"


# Global settings instance
settings = Settings()
