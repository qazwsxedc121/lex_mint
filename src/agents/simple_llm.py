"""简单的 LLM 调用服务 - 不使用 LangGraph"""

import os
import logging
from typing import List, Dict, Any, AsyncIterator
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage

from src.utils.llm_logger import get_llm_logger

logger = logging.getLogger(__name__)


def call_llm(messages: List[Dict[str, str]], session_id: str = "unknown") -> str:
    """直接调用 LLM，不使用 LangGraph.

    Args:
        messages: 消息列表 [{"role": "user/assistant", "content": "..."}]
        session_id: 会话 ID（用于日志）

    Returns:
        AI 的回复内容
    """
    llm_logger = get_llm_logger()

    print(f"🔧 准备调用 DeepSeek")
    print(f"   会话历史消息数: {len(messages)}")
    logger.info(f"🔧 准备调用 DeepSeek，消息数: {len(messages)}")

    # 初始化 LLM
    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.7,
        base_url="https://api.deepseek.com",
        api_key=os.getenv("DEEPSEEK_API_KEY")
    )

    # 转换消息格式
    langchain_messages = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            langchain_messages.append(HumanMessage(content=msg["content"]))
            print(f"   消息 {i+1}: 用户 - {msg['content'][:50]}...")
        elif msg.get("role") == "assistant":
            langchain_messages.append(AIMessage(content=msg["content"]))
            print(f"   消息 {i+1}: 助手 - {msg['content'][:50]}...")

    try:
        print(f"🚀 正在发送 {len(langchain_messages)} 条消息到 DeepSeek API...")
        logger.info(f"🚀 调用 DeepSeek API...")

        # 调用 LLM（只调用一次！）
        response = llm.invoke(langchain_messages)

        print(f"✅ 收到 DeepSeek 回复，长度: {len(response.content)} 字符")
        logger.info(f"✅ 收到回复: {len(response.content)} 字符")

        # 记录日志
        llm_logger.log_interaction(
            session_id=session_id,
            messages_sent=langchain_messages,
            response_received=response,
            model="deepseek-chat"
        )
        print(f"📝 LLM 交互已记录到日志文件")

        return response.content

    except Exception as e:
        print(f"❌ DeepSeek API 调用失败: {str(e)}")
        logger.error(f"❌ API 调用失败: {str(e)}", exc_info=True)
        llm_logger.log_error(session_id, e, context="LLM API call")
        raise


async def call_llm_stream(
    messages: List[Dict[str, str]],
    session_id: str = "unknown"
) -> AsyncIterator[str]:
    """流式调用 LLM，逐token返回.

    Args:
        messages: 消息列表 [{"role": "user/assistant", "content": "..."}]
        session_id: 会话 ID（用于日志）

    Yields:
        AI 回复的每个 token
    """
    llm_logger = get_llm_logger()

    print(f"🔧 准备流式调用 DeepSeek")
    print(f"   会话历史消息数: {len(messages)}")
    logger.info(f"🔧 准备流式调用 DeepSeek，消息数: {len(messages)}")

    # 初始化 LLM (streaming=True)
    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.7,
        base_url="https://api.deepseek.com",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        streaming=True  # 启用流式输出
    )

    # 转换消息格式
    langchain_messages = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            langchain_messages.append(HumanMessage(content=msg["content"]))
            print(f"   消息 {i+1}: 用户 - {msg['content'][:50]}...")
        elif msg.get("role") == "assistant":
            langchain_messages.append(AIMessage(content=msg["content"]))
            print(f"   消息 {i+1}: 助手 - {msg['content'][:50]}...")

    try:
        print(f"🚀 正在流式发送 {len(langchain_messages)} 条消息到 DeepSeek API...")
        logger.info(f"🚀 流式调用 DeepSeek API...")

        # 收集完整回复用于日志记录
        full_response = ""

        # 流式调用 LLM
        async for chunk in llm.astream(langchain_messages):
            if chunk.content:
                full_response += chunk.content
                yield chunk.content

        print(f"✅ DeepSeek 流式回复完成，总长度: {len(full_response)} 字符")
        logger.info(f"✅ 流式回复完成: {len(full_response)} 字符")

        # 记录完整交互到日志
        from langchain_core.messages import AIMessage as AIMsg
        response_msg = AIMsg(content=full_response)
        llm_logger.log_interaction(
            session_id=session_id,
            messages_sent=langchain_messages,
            response_received=response_msg,
            model="deepseek-chat"
        )
        print(f"📝 流式 LLM 交互已记录到日志文件")

    except Exception as e:
        print(f"❌ DeepSeek 流式 API 调用失败: {str(e)}")
        logger.error(f"❌ 流式 API 调用失败: {str(e)}", exc_info=True)
        llm_logger.log_error(session_id, e, context="LLM Stream API call")
        raise
