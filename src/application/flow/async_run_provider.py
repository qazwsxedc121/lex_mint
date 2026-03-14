"""Shared async run service/store singletons."""

from __future__ import annotations

from src.application.orchestration import OrchestrationEngine, SqliteRunStore
from src.application.workflows import WorkflowExecutionService

from .async_run_service import AsyncRunService
from src.infrastructure.storage.async_run_store_service import AsyncRunStoreService
from .flow_stream_runtime_provider import get_flow_stream_runtime
from src.infrastructure.config.workflow_config_service import WorkflowConfigService

_async_run_store = AsyncRunStoreService()
_orchestration_run_store = SqliteRunStore()
_async_run_service = AsyncRunService(
    store=_async_run_store,
    runtime=get_flow_stream_runtime(),
    workflow_config_service=WorkflowConfigService(),
    workflow_execution_service=WorkflowExecutionService(
        orchestration_engine=OrchestrationEngine(run_store=_orchestration_run_store),
    ),
)


def get_async_run_store() -> AsyncRunStoreService:
    return _async_run_store


def get_async_run_service() -> AsyncRunService:
    return _async_run_service
