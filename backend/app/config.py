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
    environment: str = "development"

    # Security
    app_secret_key: str = "dev-secret-key-change-in-production-min32"
    jwt_secret_key: str = "dev-jwt-secret-key-change-in-prod-min32"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/integrate_health"

    # AWS Configuration
    aws_region: str = "us-east-1"
    s3_bucket_name: str = ""  # Required for AWS deployment
    s3_audio_prefix: str = "audio/"  # Prefix for audio files in S3

    # Whisper Service (self-hosted transcription)
    whisper_service_url: str = "http://localhost:8080"
    whisper_timeout_seconds: int = 300  # 5 minutes for long audio

    # AWS Bedrock (LLM for note generation)
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    bedrock_max_tokens: int = 4096
    bedrock_temperature: float = 0.3

    # Legacy External Services (kept for backward compatibility during migration)
    # These will be removed after full AWS migration
    deepgram_api_key: str = ""
    anthropic_api_key: str = ""

    # Storage Mode: "local" for local filesystem, "s3" for AWS S3
    storage_mode: str = "local"

    # File Upload (local storage settings)
    upload_dir: str = "uploads"
    max_audio_size_mb: int = 100
    allowed_audio_formats: list[str] = ["wav", "mp3", "m4a", "webm", "ogg"]

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
