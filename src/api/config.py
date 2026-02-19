"""Configuration management using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from pathlib import Path
from typing import List
import os


def _default_cors_origins() -> List[str]:
    """Build sane CORS defaults without hardcoded project port literals."""
    frontend_port = os.getenv("FRONTEND_PORT", "").strip()
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    if frontend_port:
        origins = [
            f"http://localhost:{frontend_port}",
            f"http://127.0.0.1:{frontend_port}",
            *origins,
        ]
    return origins


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int

    # Storage Configuration
    conversations_dir: Path = Path("conversations")
    attachments_dir: Path = Path("attachments")
    max_file_size_mb: int = 10

    # Project Configuration
    projects_config_path: Path = Path("data/state/projects_config.yaml")
    projects_browse_roots: List[Path] = [Path(".")]
    max_file_read_size_mb: int = 10
    allowed_file_extensions: List[str] = [
        ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx",
        ".json", ".yaml", ".yml", ".html", ".css", ".xml",
        ".java", ".c", ".cpp", ".h", ".go", ".rs", ".sql"
    ]

    # CORS Configuration
    cors_origins: List[str] = Field(default_factory=_default_cors_origins)

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("projects_browse_roots", mode="before")
    @classmethod
    def parse_projects_browse_roots(cls, value):
        if value in (None, ""):
            return [Path(".")]
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",") if part.strip()]
            return [Path(os.path.expandvars(part)).expanduser() for part in parts]
        if isinstance(value, list):
            return [Path(os.path.expandvars(str(part))).expanduser() for part in value]
        return value


# Global settings instance
settings = Settings()
