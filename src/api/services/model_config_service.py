"""Compatibility re-export for model configuration service.

This module historically exposed both ``ModelConfigService`` and several helper symbols
that tests monkeypatch directly (for example ``config_defaults_dir`` and
``AdapterRegistry``). Keep these names here while the implementation lives under
``src.infrastructure.config``.
"""

from __future__ import annotations

from src.infrastructure.config import model_config_service as _impl

ModelConfigService = _impl.ModelConfigService

# Re-export patchable helpers for backward compatibility.
AdapterRegistry = _impl.AdapterRegistry
config_defaults_dir = _impl.config_defaults_dir
config_local_dir = _impl.config_local_dir
legacy_config_dir = _impl.legacy_config_dir
local_keys_config_path = _impl.local_keys_config_path
shared_keys_config_path = _impl.shared_keys_config_path
ensure_local_file = _impl.ensure_local_file

__all__ = [
    "ModelConfigService",
    "AdapterRegistry",
    "config_defaults_dir",
    "config_local_dir",
    "legacy_config_dir",
    "local_keys_config_path",
    "shared_keys_config_path",
    "ensure_local_file",
]
