"""Simple agent implementation using LangGraph."""

from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage

from src.state.agent_state import SimpleAgentState
from src.utils.llm_logger import get_llm_logger
from src.api.services.model_config_service import ModelConfigService


def chat_node(state: SimpleAgentState) -> Dict[str, Any]:
    """Process user input and generate response."""
    import logging
    logger = logging.getLogger(__name__)

    messages = state["messages"]
    llm_logger = get_llm_logger()

    # Get session_id from state metadata if available, otherwise use "unknown"
    session_id = state.get("session_id", "unknown")

    print(f"🔧 chat_node: 准备调用 DeepSeek")
    print(f"   会话历史消息数: {len(messages)}")
    logger.info(f"🔧 chat_node: 准备调用 DeepSeek")
    logger.info(f"   会话历史消息数: {len(messages)}")

    model_service = ModelConfigService()
    provider = model_service.get_model_and_provider_sync("deepseek:deepseek-chat")[1]
    api_key = model_service.resolve_provider_api_key_sync(provider)

    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.7,
        base_url=provider.base_url,
        api_key=api_key,
    )

    langchain_messages = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            langchain_messages.append(HumanMessage(content=msg["content"]))
            print(f"   消息 {i+1}: 用户 - {msg['content'][:50]}...")
            logger.info(f"   消息 {i+1}: 用户 - {msg['content'][:50]}...")
        elif msg.get("role") == "assistant":
            langchain_messages.append(AIMessage(content=msg["content"]))
            print(f"   消息 {i+1}: 助手 - {msg['content'][:50]}...")
            logger.info(f"   消息 {i+1}: 助手 - {msg['content'][:50]}...")

    try:
        # Log the request before sending
        print(f"🚀 正在发送 {len(langchain_messages)} 条消息到 DeepSeek API...")
        logger.info(f"🚀 正在发送 {len(langchain_messages)} 条消息到 DeepSeek API...")
        llm_logger.logger.info(f"Sending {len(langchain_messages)} messages to DeepSeek for session {session_id}")

        # Make the LLM call
        response = llm.invoke(langchain_messages)

        print(f"✅ 收到 DeepSeek 回复，长度: {len(response.content)} 字符")
        logger.info(f"✅ 收到 DeepSeek 回复，长度: {len(response.content)} 字符")

        # Log the complete interaction
        llm_logger.log_interaction(
            session_id=session_id,
            messages_sent=langchain_messages,
            response_received=response,
            model="deepseek-chat"
        )
        print(f"📝 LLM 交互已记录到日志文件")
        logger.info(f"📝 LLM 交互已记录到日志文件")

    except Exception as e:
        print(f"❌ DeepSeek API 调用失败: {str(e)}")
        logger.error(f"❌ DeepSeek API 调用失败: {str(e)}", exc_info=True)
        llm_logger.log_error(session_id, e, context="chat_node LLM invocation")
        raise

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
