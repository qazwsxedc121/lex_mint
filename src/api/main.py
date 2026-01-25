"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# 1. 最先加载环境变量
load_dotenv()

# 2. 立即初始化日志系统 (在导入其他模块之前)
from .logging_config import setup_logging
setup_logging()

import logging

from .routers import sessions, chat, models
from .config import settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title="LangGraph Agent API",
    description="Web API for LangGraph-based AI agent with conversation persistence",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(models.router)

logger.info("=" * 80)
logger.info("FastAPI Application Started")
logger.info(f"CORS Origins: {settings.cors_origins}")
logger.info(f"Conversations Dir: {settings.conversations_dir}")
logger.info("=" * 80)


@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    logger.info("=== 应用启动初始化 ===")

    # 初始化模型配置（如果不存在则创建默认配置）
    from .services.model_config_service import ModelConfigService
    model_service = ModelConfigService()
    # 构造函数中已经调用 _ensure_config_exists()

    logger.info("✅ 模型配置初始化完成")


@app.get("/api/health")
async def health_check():
    """Health check endpoint.

    Returns:
        {"status": "ok"}
    """
    return {"status": "ok"}


@app.get("/")
async def root():
    """Root endpoint with API information.

    Returns:
        API welcome message and documentation link
    """
    return {
        "message": "LangGraph Agent API",
        "docs": "/docs",
        "health": "/api/health"
    }
