"""Agent service for processing chat messages - 简化版（不使用 LangGraph）"""

from typing import Dict, AsyncIterator
import logging
import asyncio

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
        model_id = session.get("model_id")  # 获取会话的模型 ID
        print(f"✅ 会话加载完成，当前有 {len(messages)} 条消息，模型: {model_id}")

        print(f"🧠 [步骤 3] 调用 LLM...")
        logger.info(f"🧠 [步骤 3] 调用 LLM")

        # 直接调用 LLM（只调用一次！），传递 model_id
        assistant_message = call_llm(messages, session_id=session_id, model_id=model_id)

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
        user_message: str,
        skip_user_append: bool = False
    ) -> AsyncIterator[str]:
        """流式处理用户消息并返回 AI 响应流.

        Args:
            session_id: Session UUID
            user_message: User's input text
            skip_user_append: 是否跳过追加用户消息（重新生成时使用）

        Yields:
            AI assistant's response tokens

        Raises:
            FileNotFoundError: If session doesn't exist
        """
        # 仅当 skip_user_append=False 时追加用户消息
        if not skip_user_append:
            print(f"📝 [步骤 1] 保存用户消息到文件...")
            logger.info(f"📝 [步骤 1] 保存用户消息")
            await self.storage.append_message(session_id, "user", user_message)
            print(f"✅ 用户消息已保存")
        else:
            print(f"⏭️ [步骤 1] 跳过保存用户消息（重新生成模式）")
            logger.info(f"⏭️ [步骤 1] 跳过保存用户消息")

        print(f"📂 [步骤 2] 加载会话状态...")
        logger.info(f"📂 [步骤 2] 加载会话状态")
        session = await self.storage.get_session(session_id)
        messages = session["state"]["messages"]
        assistant_id = session.get("assistant_id")
        model_id = session.get("model_id")
        print(f"✅ 会话加载完成，当前有 {len(messages)} 条消息")
        print(f"   助手ID: {assistant_id}, 模型: {model_id}")

        # 获取助手配置（包括系统提示词和最大对话轮数）
        system_prompt = None
        max_rounds = None

        # 检查是否是 legacy 会话标识
        if assistant_id and assistant_id.startswith("__legacy_model_"):
            # 旧会话：只使用 model_id，不使用助手配置
            print(f"   使用旧会话模式（仅模型）")
        elif assistant_id:
            # 新会话：从助手配置加载系统提示词和对话轮数限制
            from .assistant_config_service import AssistantConfigService
            assistant_service = AssistantConfigService()
            try:
                assistant = await assistant_service.get_assistant(assistant_id)
                if assistant:
                    system_prompt = assistant.system_prompt
                    max_rounds = assistant.max_rounds
                    print(f"   使用助手配置:")
                    if system_prompt:
                        print(f"     - 系统提示词: {system_prompt[:50]}...")
                    if max_rounds:
                        if max_rounds == -1:
                            print(f"     - 对话轮数: 无限制")
                        else:
                            print(f"     - 最大轮数: {max_rounds}")
            except Exception as e:
                logger.warning(f"   加载助手配置失败: {e}，使用默认配置")

        print(f"🧠 [步骤 3] 流式调用 LLM...")
        logger.info(f"🧠 [步骤 3] 流式调用 LLM")

        # 收集完整回复用于保存
        full_response = ""

        try:
            # 流式调用 LLM，传递 model_id、system_prompt 和 max_rounds
            async for chunk in call_llm_stream(
                messages,
                session_id=session_id,
                model_id=model_id,
                system_prompt=system_prompt,
                max_rounds=max_rounds
            ):
                full_response += chunk
                yield chunk

            print(f"✅ LLM 流式处理完成")
            logger.info(f"✅ LLM 流式处理完成")
            print(f"💬 AI 回复总长度: {len(full_response)} 字符")

        except asyncio.CancelledError:
            # 流式中止，保存部分内容
            print(f"⚠️ 流式生成被中止，保存部分内容...")
            logger.warning(f"⚠️ 流式生成被中止，保存部分内容（{len(full_response)} 字符）")
            if full_response:
                await self.storage.append_message(session_id, "assistant", full_response)
                print(f"✅ 部分 AI 回复已保存")
            raise

        print(f"📝 [步骤 4] 保存完整 AI 回复到文件...")
        logger.info(f"📝 [步骤 4] 保存完整 AI 回复")
        await self.storage.append_message(session_id, "assistant", full_response)
        print(f"✅ AI 回复已保存")
