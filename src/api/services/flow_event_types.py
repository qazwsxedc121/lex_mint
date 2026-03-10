"""Compatibility re-export for flow event type constants."""

from src.application.flow import flow_event_types as _flow_event_types

__all__ = [name for name in dir(_flow_event_types) if name.isupper()]

globals().update({name: getattr(_flow_event_types, name) for name in __all__})
