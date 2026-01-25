"""State definitions for the agent system."""

from typing import TypedDict, Annotated, List, Dict, Any, Optional
from operator import add


class SimpleAgentState(TypedDict, total=False):
    """State for the simple agent."""

    messages: Annotated[List[Dict[str, Any]], add]
    current_step: int
    session_id: str  # Session ID for logging and tracking (optional)
