"""Configuration management using Pydantic Settings.

Settings are loaded from environment variables with LIQUIDITY_ prefix,
or from .env file for local development.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class CircuitBreakerSettings(BaseSettings):
    """Circuit breaker configuration."""

    model_config = SettingsConfigDict(env_prefix="LIQUIDITY_CB_")

    threshold: int = Field(
        default=5,
        description="Number of failures before circuit opens",
    )
    ttl: int = Field(
        default=60,
        description="Seconds before half-open state",
    )


class RetrySettings(BaseSettings):
    """Retry configuration."""

    model_config = SettingsConfigDict(env_prefix="LIQUIDITY_RETRY_")

    max_attempts: int = Field(
        default=5,
        description="Maximum number of retry attempts",
    )
    multiplier: float = Field(
        default=1.0,
        description="Exponential backoff multiplier",
    )
    min_wait: int = Field(
        default=1,
        description="Minimum wait time in seconds",
    )
    max_wait: int = Field(
        default=60,
        description="Maximum wait time in seconds",
    )


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Environment variables use LIQUIDITY_ prefix.
    Example: LIQUIDITY_QUESTDB_HOST=localhost

    For secrets, use SOPS+age encryption and load via environment.
    """

    model_config = SettingsConfigDict(
        env_prefix="LIQUIDITY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # API Keys (loaded from environment, use SOPS for encryption)
    # Accepts both LIQUIDITY_FRED_API_KEY and FRED_API_KEY (for OpenBB compatibility)
    fred_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="FRED API key for data fetching",
        validation_alias=AliasChoices("LIQUIDITY_FRED_API_KEY", "FRED_API_KEY"),
    )

    # EIA API key for petroleum data
    # Accepts both LIQUIDITY_EIA_API_KEY and EIA_API_KEY
    eia_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="EIA API key for petroleum data fetching",
        validation_alias=AliasChoices("LIQUIDITY_EIA_API_KEY", "EIA_API_KEY"),
    )

    # QuestDB configuration
    questdb_host: str = Field(
        default="localhost",
        description="QuestDB host address",
    )
    questdb_port: int = Field(
        default=9009,
        description="QuestDB ILP port",
    )
    questdb_http_port: int = Field(
        default=9000,
        description="QuestDB HTTP port for queries",
    )

    # Redis configuration
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL",
    )

    # Prometheus configuration
    prometheus_port: int = Field(
        default=8000,
        description="Prometheus metrics exposition port",
    )

    # Nested settings
    circuit_breaker: CircuitBreakerSettings = Field(
        default_factory=CircuitBreakerSettings,
        description="Circuit breaker configuration",
    )
    retry: RetrySettings = Field(
        default_factory=RetrySettings,
        description="Retry configuration",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )

    @property
    def questdb_ilp_uri(self) -> str:
        """Get QuestDB ILP connection URI."""
        return f"{self.questdb_host}:{self.questdb_port}"

    @property
    def questdb_http_uri(self) -> str:
        """Get QuestDB HTTP connection URI."""
        return f"http://{self.questdb_host}:{self.questdb_http_port}"

    @property
    def cache_dir(self) -> Path:
        """Get cache directory for bulk downloads.

        Returns:
            Path to cache directory, created if it doesn't exist.
        """
        from pathlib import Path

        cache_path = Path.home() / ".cache" / "liquidity-monitor"
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization validation."""
        # Load nested settings from environment if not provided
        if self.circuit_breaker is None:
            self.circuit_breaker = CircuitBreakerSettings()
        if self.retry is None:
            self.retry = RetrySettings()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Uses lru_cache to ensure a single Settings instance is created
    and reused across the application.

    Returns:
        Settings instance with configuration values.
    """
    return Settings()
