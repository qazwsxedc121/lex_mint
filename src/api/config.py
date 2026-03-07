"""Configuration management using pydantic-settings."""

import os
from pathlib import Path
import re
from typing import TYPE_CHECKING, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .paths import attachments_dir, conversations_dir, data_state_dir, user_data_root

_WINDOWS_DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


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


def _normalize_storage_path(value) -> Path:
    raw = os.path.expandvars(str(value))
    candidate = Path(raw).expanduser()
    if os.name != "nt" and _WINDOWS_DRIVE_PATH_RE.match(raw):
        return candidate
    if candidate.is_absolute():
        return candidate.resolve()
    return user_data_root() / candidate


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int

    # Storage Configuration
    conversations_dir: Path = Field(default_factory=conversations_dir)
    attachments_dir: Path = Field(default_factory=attachments_dir)
    max_file_size_mb: int = 10

    # Project Configuration
    projects_config_path: Path = Field(default_factory=lambda: data_state_dir() / "projects_config.yaml")
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

    # Flow stream replay/resume runtime
    flow_stream_ttl_seconds: int = 900
    flow_stream_max_events: int = 5000
    flow_stream_max_active: int = 200

    # Project chat pending patch confirmation window
    project_chat_pending_patch_ttl_seconds: int = 3600

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

    @field_validator("conversations_dir", "attachments_dir", "projects_config_path", mode="before")
    @classmethod
    def normalize_storage_paths(cls, value):
        return _normalize_storage_path(value)


# Global settings instance
if TYPE_CHECKING:
    settings = Settings(api_port=8000)
else:
    settings = Settings()
