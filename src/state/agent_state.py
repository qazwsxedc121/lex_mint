"""State definitions for the agent system."""

from typing import TypedDict, Annotated, List, Dict, Any
from operator import add


class SimpleAgentState(TypedDict):
    """State for the simple agent."""
    
    messages: Annotated[List[Dict[str, Any]], add]
    current_step: int
