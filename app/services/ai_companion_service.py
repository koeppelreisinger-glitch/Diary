import logging
from typing import List

from app.core.config import settings
from app.core.exceptions import ErrorResponseAPIException
from app.models.conversation import ConversationMessage
from app.services.tokenhub_chat_service import TokenHubChatService

logger = logging.getLogger(__name__)


class AICompanionService:
    async def generate_reply(self, messages: List[ConversationMessage], mode: str | None = None) -> str:
        user_texts = [message.content for message in messages if message.role == "user"]
        if not user_texts:
            return "我随时准备好听你说说今天发生了什么。"

        if not settings.TOKENHUB_AUTHORIZATION and not settings.TOKENHUB_API_KEY:
            logger.warning("TokenHub credentials are not configured, using local fallback reply")
            return self._fallback_reply(messages)

        try:
            reply_text = await TokenHubChatService().create_text_completion(
                self._build_chat_messages(messages, mode),
                temperature=settings.TOKENHUB_TEMPERATURE,
            )
        except ErrorResponseAPIException:
            raise
        except Exception as exc:
            logger.exception("TokenHub chat completion failed")
            raise ErrorResponseAPIException(
                status_code=502,
                detail=f"AI 助手服务暂时不可用：{exc}",
                code=50201,
            ) from exc

        if not reply_text.strip():
            raise ErrorResponseAPIException(
                status_code=502,
                detail="AI 助手返回了空内容",
                code=50202,
            )

        return reply_text.strip()

    def _build_chat_messages(self, messages: List[ConversationMessage], mode: str | None = None) -> list[dict]:
        chat_messages: list[dict] = []
        
        # 1. 提取预加载的系统指令（如果有的话）
        # 我们假设 sequence_number 为 0 的是系统指令
        system_msg = next((m for m in messages if m.role == "system"), None)
        
        if system_msg:
            chat_messages.append({"role": "system", "content": system_msg.content})
        else:
            # 兜底：如果数据库里没找到，则使用代码中的默认指令
            chat_messages.append({"role": "system", "content": settings.TOKENHUB_CHAT_SYSTEM_PROMPT})

        # 2. 注入回复风格优化指令
        chat_messages.append({
            "role": "system", 
            "content": "【回复风格】保持自然对话感，极其精简，避免冗长重复。字数严格控制在 30 字以内。优先直接回应用户内容。"
        })
        
        # 3. 处理模式特定的指令
        if mode:
            mode_prompts = {
                "expense": "记账模式：你是干练管家，仅确认金额分类，不寒暄。",
                "inspiration": "灵感模式：你是细腻知音，肯定价值并引发深度共鸣。",
                "learning": "学习模式：你是热血同伴，强调积累并给予成就反馈。",
                "chat": "闲聊模式：你是温柔电台，只做情绪承接，不做逻辑分析。"
            }
            mode_content = mode_prompts.get(mode, '')
            if mode_content:
                chat_messages.append({"role": "system", "content": mode_content})
            
            chat_messages.append({
                "role": "system", 
                "content": "提问引导：少量是非题。询问实质性开放问题，引导描述细节、感受或过程。"
            })
        
        # 4. 加入最近的对话上下文
        # 排除掉系统消息后，取最近的 N 条
        other_messages = [m for m in messages if m.role in ("user", "ai")]
        recent_messages = other_messages[-settings.TOKENHUB_CHAT_CONTEXT_LIMIT:]
        
        for message in recent_messages:
            role = "assistant" if message.role == "ai" else "user"
            content = (message.content or "").strip()

            image_url = getattr(message, "image_url", None)
            if image_url and role == "user":
                parts: list[dict] = [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url, "detail": "auto"},
                    }
                ]
                if content:
                    parts.append({"type": "text", "text": content})
                chat_messages.append({"role": role, "content": parts})
            else:
                if not content:
                    continue
                chat_messages.append({"role": role, "content": content})

        return chat_messages
    def _fallback_reply(self, messages: List[ConversationMessage]) -> str:
        return "我记下来了。然后呢？今天还有哪个人、哪个地方，或者哪件小事，是你其实不想把它忘掉的？"
