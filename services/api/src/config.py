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

    # Proxmox (VM management)
    proxmox_base_url: str = Field(
        default="https://192.168.50.180:8006",
        description="Proxmox API base URL (e.g., https://host:8006)",
    )
    proxmox_token_id: Optional[str] = Field(
        default=None,
        description="Proxmox API token ID (user@realm!token)",
    )
    proxmox_token_secret: Optional[str] = Field(
        default=None,
        description="Proxmox API token secret",
    )
    proxmox_verify_ssl: bool = Field(
        default=False,
        description="Verify SSL cert when calling Proxmox (often self-signed)",
    )

    # qBittorrent (torrent management)
    qb_base_url: str = Field(
        default="http://gluetun:8080",
        description="qBittorrent base URL (gluetun exposes qb at 8080 in-cluster)",
    )
    qb_username: str = Field(default="admin", description="qBittorrent username")
    qb_password: Optional[str] = Field(
        default=None, description="qBittorrent password (set via UI/env)"
    )

    # Search backends
    meili_url: str = Field(
        default="http://meilisearch:7700",
        description="Meilisearch base URL",
    )
    meili_api_key: Optional[str] = Field(
        default=None, description="Meilisearch API key (master/search key)"
    )
    meili_index: str = Field(default="files", description="Meilisearch index name")
    searx_url: str = Field(
        default="http://searxng:8080",
        description="SearXNG base URL",
    )

    # Router/AI stack URLs
    router_url: str = Field(default="http://router:8000", description="Agent router base URL")
    ai_stack_url: str = Field(default="http://ai-stack:8090", description="AI stack base URL")

    # AI workflow configuration
    ai_repos: str = Field(
        default=(
            "https://github.com/mhold3n/Birtha_bigger_n_badder,"
            "https://github.com/mhold3n/WrkHrs,"
            "https://github.com/datalab-to/marker"
        ),
        description="Comma-separated list of repositories for code-RAG workflows",
    )
    marker_docs_dir: str = Field(
        default="/mnt/appdata/addons/documents",
        description="Host path for marker input documents (if mounted)",
    )
    marker_processed_dir: str = Field(
        default="/mnt/appdata/addons/documents_processed",
        description="Host path for marker processed documents (if mounted)",
    )

    def model_post_init(self, __context) -> None:
        """Validate configuration after initialization."""
        if self.debug and not self.jwt_secret:
            self.jwt_secret = "dev-secret-key"
        if self.debug and not self.encryption_key:
            self.encryption_key = "dev-encryption-key-32-chars"


# Global settings instance
settings = Settings()
