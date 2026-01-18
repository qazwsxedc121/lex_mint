"""Simple agent implementation using LangGraph."""

import os
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage

from src.state.agent_state import SimpleAgentState


def chat_node(state: SimpleAgentState) -> Dict[str, Any]:
    """Process user input and generate response."""
    messages = state["messages"]
    
    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.7,
        base_url="https://api.deepseek.com",
        api_key=os.getenv("DEEPSEEK_API_KEY")
    )
    
    langchain_messages = []
    for msg in messages:
        if msg.get("role") == "user":
            langchain_messages.append(HumanMessage(content=msg["content"]))
        elif msg.get("role") == "assistant":
            langchain_messages.append(AIMessage(content=msg["content"]))
    
    response = llm.invoke(langchain_messages)
    
    new_message = {"role": "assistant", "content": response.content}
    
    return {"messages": [new_message], "current_step": state["current_step"] + 1}


def should_continue(state: SimpleAgentState) -> str:
    """Determine if the agent should continue processing."""
    if state["current_step"] >= 10:
        return "end"
    return "continue"


def create_simple_agent() -> StateGraph:
    """Create and configure the simple agent graph."""
    workflow = StateGraph(SimpleAgentState)
    
    workflow.add_node("chat", chat_node)
    
    workflow.set_entry_point("chat")
    
    workflow.add_conditional_edges(
        "chat",
        should_continue,
        {
            "continue": "chat",
            "end": END
        }
    )
    
    return workflow.compile()
