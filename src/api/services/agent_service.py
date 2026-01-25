"""Agent service for processing chat messages."""

from typing import Dict
import logging

from src.agents.simple_agent import create_simple_agent
from .conversation_storage import ConversationStorage

logger = logging.getLogger(__name__)


class AgentService:
    """Service layer for agent interactions with conversation storage.

    Coordinates the flow:
    1. Append user message to storage
    2. Load current conversation state
    3. Invoke agent to generate response
    4. Append assistant response to storage
    5. Return response to caller
    """

    def __init__(self, storage: ConversationStorage):
        """Initialize agent service.

        Args:
            storage: ConversationStorage instance for persistence
        """
        self.agent = create_simple_agent()
        self.storage = storage
        logger.info("🤖 AgentService 初始化完成")

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
        logger.info(f"📝 [步骤 1] 保存用户消息到文件...")
        # 1. Append user message to file
        await self.storage.append_message(session_id, "user", user_message)
        print(f"✅ 用户消息已保存")
        logger.info(f"✅ 用户消息已保存")

        print(f"📂 [步骤 2] 加载会话状态...")
        logger.info(f"📂 [步骤 2] 加载会话状态...")
        # 2. Get current session state
        session = await self.storage.get_session(session_id)
        state = session["state"]
        print(f"✅ 会话加载完成，当前有 {len(state['messages'])} 条消息")
        logger.info(f"✅ 会话加载完成，当前有 {len(state['messages'])} 条消息")

        # 3. Add session_id to state for logging
        state["session_id"] = session_id

        print(f"🧠 [步骤 3] 调用 Agent 处理...")
        print(f"   准备调用 DeepSeek LLM...")
        logger.info(f"🧠 [步骤 3] 调用 Agent 处理...")
        logger.info(f"   准备调用 DeepSeek LLM...")
        # 4. Invoke agent with current state
        # Note: The agent expects a state dict with messages and current_step
        result = self.agent.invoke(state)
        print(f"✅ Agent 处理完成")
        logger.info(f"✅ Agent 处理完成")

        # 5. Extract AI response (last message should be assistant's)
        assistant_message = result["messages"][-1]["content"]
        print(f"💬 AI 回复长度: {len(assistant_message)} 字符")
        logger.info(f"💬 AI 回复长度: {len(assistant_message)} 字符")

        print(f"📝 [步骤 4] 保存 AI 回复到文件...")
        logger.info(f"📝 [步骤 4] 保存 AI 回复到文件...")
        # 6. Append AI response to file
        await self.storage.append_message(session_id, "assistant", assistant_message)
        print(f"✅ AI 回复已保存")
        logger.info(f"✅ AI 回复已保存")

        return assistant_message
