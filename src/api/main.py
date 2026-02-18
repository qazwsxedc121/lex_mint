"""FastAPI application entry point."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables before importing runtime config/services.
load_dotenv()

from .logging_config import setup_logging

setup_logging()

import logging

from .config import settings
from .routers import (
    assistants,
    chat,
    compression_config,
    file_reference_config,
    followup,
    folders,
    knowledge_base,
    memory,
    models,
    projects,
    prompt_templates,
    rag_config,
    search_config,
    sessions,
    title_generation,
    translation,
    translation_config,
    tts,
    tts_config,
    webpage_config,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="LangGraph Agent API",
    description="Web API for LangGraph-based AI agent with conversation persistence",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Register routers
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(models.router)
app.include_router(assistants.router)
app.include_router(title_generation.router)
app.include_router(projects.router)
app.include_router(search_config.router)
app.include_router(webpage_config.router)
app.include_router(followup.router)
app.include_router(compression_config.router)
app.include_router(file_reference_config.router)
app.include_router(translation_config.router)
app.include_router(translation.router)
app.include_router(tts_config.router)
app.include_router(tts.router)
app.include_router(rag_config.router)
app.include_router(knowledge_base.router)
app.include_router(prompt_templates.router)
app.include_router(folders.router)
app.include_router(memory.router)

logger.info("=" * 80)
logger.info("FastAPI Application Started")
logger.info("CORS Origins: %s", settings.cors_origins)
logger.info("Conversations Dir: %s", settings.conversations_dir)
logger.info("=" * 80)


@app.on_event("startup")
async def startup_event():
    """Initialize runtime config/state files and storage directories on startup."""
    logger.info("=== Application startup initialization ===")

    settings.projects_config_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize model/assistant configuration files if missing.
    from .services.model_config_service import ModelConfigService
    from .services.assistant_config_service import AssistantConfigService

    ModelConfigService()
    AssistantConfigService()

    # Initialize prompt templates and chat folders configs if missing.
    from .services.prompt_template_service import PromptTemplateConfigService
    from .services.folder_service import FolderService

    PromptTemplateConfigService()
    FolderService()

    # Migrate project conversations from conversations/projects/ to .lex_mint/
    from .services.migration_service import migrate_project_conversations

    migration_result = migrate_project_conversations(settings.conversations_dir)
    if migration_result["migrated"]:
        logger.info("Migrated %s project conversation file(s) to .lex_mint directories",
                     migration_result["migrated"])

    # Clean temporary sessions from previous runs.
    from .services.conversation_storage import create_storage_with_project_resolver

    storage = create_storage_with_project_resolver(settings.conversations_dir)
    cleaned = await storage.cleanup_temporary_sessions()
    if cleaned:
        logger.info("Cleaned up %s temporary session(s)", cleaned)

    # Ensure vector-store paths exist.
    from .services.rag_config_service import RagConfigService

    try:
        rag_cfg = RagConfigService()
        backend = str(getattr(rag_cfg.config.storage, "vector_store_backend", "chroma") or "chroma").lower()
        if backend == "sqlite_vec":
            from .services.sqlite_vec_service import SqliteVecService

            sqlite_vec = SqliteVecService()
            logger.info("SQLite vector storage ready: %s", sqlite_vec.db_path)
        else:
            persist_dir = Path(rag_cfg.config.storage.persist_directory)
            if not persist_dir.is_absolute():
                persist_dir = Path(__file__).parent.parent.parent / persist_dir
            persist_dir.mkdir(parents=True, exist_ok=True)
            logger.info("ChromaDB storage directory ready: %s", persist_dir)
    except Exception as e:
        logger.warning("Failed to initialize vector storage: %s", e)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "LangGraph Agent API",
        "docs": "/docs",
        "health": "/api/health",
    }
