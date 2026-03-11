"""Compatibility re-export for shared path helpers."""

from src.core import paths as _impl

__all__ = [name for name in dir(_impl) if not name.startswith("_")]

globals().update({name: getattr(_impl, name) for name in __all__})
