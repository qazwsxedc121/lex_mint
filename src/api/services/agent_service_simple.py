"""Agent service for processing chat messages - 简化版（不使用 LangGraph）"""

from typing import Dict, AsyncIterator
import logging

from src.agents.simple_llm import call_llm, call_llm_stream
from .conversation_storage import ConversationStorage

logger = logging.getLogger(__name__)


class AgentService:
    """Service layer for agent interactions with conversation storage.

    Coordinates the flow:
    1. Append user message to storage
    2. Load current conversation state
    3. Call LLM to generate response (直接调用，不用 LangGraph)
    4. Append assistant response to storage
    5. Return response to caller
    """

    def __init__(self, storage: ConversationStorage):
        """Initialize agent service.

        Args:
            storage: ConversationStorage instance for persistence
        """
        self.storage = storage
        logger.info("🤖 AgentService 初始化完成（简化版）")

    async def process_message(self, session_id: str, user_message: str) -> str:
        """Process a user message and return AI response.

        Args:
            session_id: Session UUID
            user_message: User's input text

        Returns:
            AI assistant's response text

        Raises:
            FileNotFoundError: If session doesn't exist
        """
        print(f"📝 [步骤 1] 保存用户消息到文件...")
        logger.info(f"📝 [步骤 1] 保存用户消息")
        await self.storage.append_message(session_id, "user", user_message)
        print(f"✅ 用户消息已保存")

        print(f"📂 [步骤 2] 加载会话状态...")
        logger.info(f"📂 [步骤 2] 加载会话状态")
        session = await self.storage.get_session(session_id)
        messages = session["state"]["messages"]
        print(f"✅ 会话加载完成，当前有 {len(messages)} 条消息")

        print(f"🧠 [步骤 3] 调用 LLM...")
        logger.info(f"🧠 [步骤 3] 调用 LLM")

        # 直接调用 LLM（只调用一次！）
        assistant_message = call_llm(messages, session_id=session_id)

        print(f"✅ LLM 处理完成")
        logger.info(f"✅ LLM 处理完成")
        print(f"💬 AI 回复长度: {len(assistant_message)} 字符")

        print(f"📝 [步骤 4] 保存 AI 回复到文件...")
        logger.info(f"📝 [步骤 4] 保存 AI 回复")
        await self.storage.append_message(session_id, "assistant", assistant_message)
        print(f"✅ AI 回复已保存")

        return assistant_message

    async def process_message_stream(
        self,
        session_id: str,
        user_message: str
    ) -> AsyncIterator[str]:
        """流式处理用户消息并返回 AI 响应流.

        Args:
            session_id: Session UUID
            user_message: User's input text

        Yields:
            AI assistant's response tokens

        Raises:
            FileNotFoundError: If session doesn't exist
        """
        print(f"📝 [步骤 1] 保存用户消息到文件...")
        logger.info(f"📝 [步骤 1] 保存用户消息")
        await self.storage.append_message(session_id, "user", user_message)
        print(f"✅ 用户消息已保存")

        print(f"📂 [步骤 2] 加载会话状态...")
        logger.info(f"📂 [步骤 2] 加载会话状态")
        session = await self.storage.get_session(session_id)
        messages = session["state"]["messages"]
        print(f"✅ 会话加载完成，当前有 {len(messages)} 条消息")

        print(f"🧠 [步骤 3] 流式调用 LLM...")
        logger.info(f"🧠 [步骤 3] 流式调用 LLM")

        # 收集完整回复用于保存
        full_response = ""

        # 流式调用 LLM
        async for chunk in call_llm_stream(messages, session_id=session_id):
            full_response += chunk
            yield chunk

        print(f"✅ LLM 流式处理完成")
        logger.info(f"✅ LLM 流式处理完成")
        print(f"💬 AI 回复总长度: {len(full_response)} 字符")

        print(f"📝 [步骤 4] 保存完整 AI 回复到文件...")
        logger.info(f"📝 [步骤 4] 保存完整 AI 回复")
        await self.storage.append_message(session_id, "assistant", full_response)
        print(f"✅ AI 回复已保存")
