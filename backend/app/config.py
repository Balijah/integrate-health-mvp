"""
Application configuration using Pydantic settings.

Loads configuration from environment variables with sensible defaults.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Integrate Health MVP"
    debug: bool = True

    # Security
    app_secret_key: str = "dev-secret-key-change-in-production-min32"
    jwt_secret_key: str = "dev-jwt-secret-key-change-in-prod-min32"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/integrate_health"

    # External Services (configured in later phases)
    deepgram_api_key: str = ""
    anthropic_api_key: str = ""

    # File Upload
    upload_dir: str = "uploads"
    max_audio_size_mb: int = 100
    allowed_audio_formats: list[str] = ["wav", "mp3", "m4a", "webm"]

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Returns:
        Settings: Application settings
    """
    return Settings()
