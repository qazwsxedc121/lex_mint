"""Code execution config API router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.routers.service_protocols import ConfigSaveServiceLike
from src.infrastructure.config.code_execution_config_service import CodeExecutionConfigService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/code-execution", tags=["code-execution"])
_ALLOWED_EXECUTION_METHODS = {"client", "server_jupyter", "server_subprocess"}
_ALLOWED_EXECUTION_BACKENDS = {"subprocess", "jupyter"}


class CodeExecutionConfigResponse(BaseModel):
    enable_client_tool_execution: bool
    enable_server_jupyter_execution: bool
    enable_server_subprocess_execution: bool
    execution_priority: list[str]
    jupyter_kernel_name: str
    # Legacy compatibility fields
    enable_server_side_tool_execution: bool
    server_side_execution_backend: str


class CodeExecutionConfigUpdate(BaseModel):
    enable_client_tool_execution: bool | None = None
    enable_server_jupyter_execution: bool | None = None
    enable_server_subprocess_execution: bool | None = None
    execution_priority: list[str] | None = None
    server_side_execution_backend: str | None = None
    enable_server_side_tool_execution: bool | None = None
    jupyter_kernel_name: str | None = None


def get_code_execution_config_service() -> CodeExecutionConfigService:
    return CodeExecutionConfigService()


@router.get("/config", response_model=CodeExecutionConfigResponse)
async def get_config(service: ConfigSaveServiceLike = Depends(get_code_execution_config_service)):
    try:
        config = service.config
        enable_server_jupyter_execution = bool(
            getattr(config, "enable_server_jupyter_execution", False)
        )
        enable_server_subprocess_execution = bool(
            getattr(config, "enable_server_subprocess_execution", False)
        )
        execution_priority = list(
            getattr(
                config,
                "execution_priority",
                ["client", "server_jupyter", "server_subprocess"],
            )
        )
        legacy_backend = "subprocess"
        for method in execution_priority:
            if method == "server_jupyter" and enable_server_jupyter_execution:
                legacy_backend = "jupyter"
                break
            if method == "server_subprocess" and enable_server_subprocess_execution:
                legacy_backend = "subprocess"
                break
        return CodeExecutionConfigResponse(
            enable_client_tool_execution=bool(
                getattr(config, "enable_client_tool_execution", True)
            ),
            enable_server_jupyter_execution=enable_server_jupyter_execution,
            enable_server_subprocess_execution=enable_server_subprocess_execution,
            execution_priority=execution_priority,
            jupyter_kernel_name=str(getattr(config, "jupyter_kernel_name", "python3")),
            enable_server_side_tool_execution=(
                enable_server_jupyter_execution or enable_server_subprocess_execution
            ),
            server_side_execution_backend=legacy_backend,
        )
    except Exception as e:
        logger.error("Failed to get code execution config: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_config(
    updates: CodeExecutionConfigUpdate,
    service: ConfigSaveServiceLike = Depends(get_code_execution_config_service),
):
    try:
        update_dict = updates.model_dump(exclude_none=True)
        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")
        priority = update_dict.get("execution_priority")
        if priority is not None:
            if not isinstance(priority, list):
                raise HTTPException(status_code=400, detail="execution_priority must be a list")
            invalid_methods = [
                str(item) for item in priority if str(item) not in _ALLOWED_EXECUTION_METHODS
            ]
            if invalid_methods:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "execution_priority contains invalid methods: " + ", ".join(invalid_methods)
                    ),
                )
            if len({str(item) for item in priority}) != len(priority):
                raise HTTPException(
                    status_code=400, detail="execution_priority contains duplicates"
                )

        backend = update_dict.pop("server_side_execution_backend", None)
        if backend is not None and str(backend) not in _ALLOWED_EXECUTION_BACKENDS:
            raise HTTPException(
                status_code=400,
                detail=(
                    "server_side_execution_backend must be one of: "
                    + ", ".join(sorted(_ALLOWED_EXECUTION_BACKENDS))
                ),
            )
        legacy_enable_server = update_dict.pop("enable_server_side_tool_execution", None)
        current_config = service.config

        if legacy_enable_server is not None:
            if bool(legacy_enable_server):
                chosen_backend = str(
                    backend
                    or getattr(current_config, "server_side_execution_backend", "subprocess")
                    or "subprocess"
                )
                update_dict["enable_server_jupyter_execution"] = chosen_backend == "jupyter"
                update_dict["enable_server_subprocess_execution"] = chosen_backend != "jupyter"
            else:
                update_dict["enable_server_jupyter_execution"] = False
                update_dict["enable_server_subprocess_execution"] = False
        elif backend is not None:
            chosen_backend = str(backend)
            update_dict["enable_server_jupyter_execution"] = chosen_backend == "jupyter"
            update_dict["enable_server_subprocess_execution"] = chosen_backend != "jupyter"
        service.save_config(update_dict)
        return {"message": "Configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update code execution config: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
