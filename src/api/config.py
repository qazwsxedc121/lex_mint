"""Configuration management using pydantic-settings."""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Configuration
    deepseek_api_key: str

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Storage Configuration
    conversations_dir: Path = Path("conversations")

    # CORS Configuration
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
