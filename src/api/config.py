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
    api_port: int = 8888

    # Storage Configuration
    conversations_dir: Path = Path("conversations")
    attachments_dir: Path = Path("attachments")
    max_file_size_mb: int = 10

    # Project Configuration
    projects_config_path: Path = Path("config/projects_config.yaml")
    max_file_read_size_mb: int = 10
    allowed_file_extensions: List[str] = [
        ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx",
        ".json", ".yaml", ".yml", ".html", ".css", ".xml",
        ".java", ".c", ".cpp", ".h", ".go", ".rs", ".sql"
    ]

    # CORS Configuration
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
