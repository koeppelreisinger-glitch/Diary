import logging
from typing import List

from app.core.config import settings
from app.core.exceptions import ErrorResponseAPIException
from app.models.conversation import ConversationMessage
from app.services.tokenhub_chat_service import TokenHubChatService

logger = logging.getLogger(__name__)


class AICompanionService:
    async def generate_reply(self, messages: List[ConversationMessage]) -> str:
        user_texts = [message.content for message in messages if message.role == "user"]
        if not user_texts:
            return "我随时准备好听你说说今天发生了什么。"

        if not settings.TOKENHUB_AUTHORIZATION and not settings.TOKENHUB_API_KEY:
            logger.warning("TokenHub credentials are not configured, using local fallback reply")
            return self._fallback_reply(messages)

        try:
            reply_text = await TokenHubChatService().create_text_completion(
                self._build_chat_messages(messages),
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

    def _build_chat_messages(self, messages: List[ConversationMessage]) -> list[dict[str, str]]:
        chat_messages: list[dict[str, str]] = [
            {"role": "system", "content": settings.TOKENHUB_CHAT_SYSTEM_PROMPT}
        ]

        recent_messages = messages[-settings.TOKENHUB_CHAT_CONTEXT_LIMIT :]
        for message in recent_messages:
            role = "assistant" if message.role == "ai" else "user"
            if role not in {"user", "assistant"}:
                continue

            content = (message.content or "").strip()
            if not content:
                continue

            chat_messages.append({"role": role, "content": content})

        return chat_messages
    def _fallback_reply(self, messages: List[ConversationMessage]) -> str:
        latest_user_text = next(
            (message.content for message in reversed(messages) if message.role == "user" and message.content),
            "",
        )

        if any(keyword in latest_user_text for keyword in ["累", "疲惫", "心累"]):
            return "听起来你今天真的很累。更像是身体累，还是心里累？有没有哪个瞬间让你特别想停下来？"

        if any(keyword in latest_user_text for keyword in ["开心", "高兴", "满足", "放松"]):
            return "这段好心情很值得记下来。是什么事情让你有这种感觉？当时你和谁在一起，或者你在哪里？"

        if any(keyword in latest_user_text for keyword in ["开会", "工作", "公司", "客户", "上班"]):
            return "听起来今天工作内容不少。最让你在意的是哪件事？它让你更紧张、疲惫，还是其实也有一点成就感？"

        if any(keyword in latest_user_text for keyword in ["咖啡", "奶茶", "外卖", "吃饭", "打车"]):
            return "我先帮你记下这个生活片段。那是在什么地方？大概花了多少钱，和谁一起吗？"

        return "我记下来了。然后呢？今天还有哪个人、哪个地方，或者哪件小事，是你其实不想把它忘掉的？"
