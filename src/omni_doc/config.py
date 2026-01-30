"""Configuration management for Omni-Doc using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Required credentials
    github_token: SecretStr = Field(
        ...,
        description="GitHub Personal Access Token for API access",
    )
    google_api_key: SecretStr = Field(
        ...,
        description="Google AI API key for Gemini access",
    )

    # Model configuration
    gemini_model: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model to use for analysis",
    )

    # Processing configuration
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for critic loop",
    )
    enable_diagrams: bool = Field(
        default=True,
        description="Enable Mermaid diagram generation",
    )

    # Logging configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Application log level",
    )

    # MCP server configuration
    mcp_server_port: int = Field(
        default=8080,
        ge=1,
        le=65535,
        description="Port for MCP HTTP server",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings: Application settings loaded from environment.
    """
    return Settings()  # type: ignore[call-arg]
