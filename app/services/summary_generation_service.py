import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import (
    ConflictException,
    ErrorResponseAPIException,
    ForbiddenException,
    NotFoundException,
)
from app.models.base import utc_now
from app.models.conversation import Conversation, ConversationMessage
from app.models.daily_record import (
    DailyRecord,
    RecordEmotion,
    RecordEvent,
    RecordExpense,
    RecordLocation,
    RecordInspiration,
)
from app.services.diary_ai_service import DiaryAIService


class SummaryGenerationService:
    def _get_user_id(self, current_user: Any) -> uuid.UUID:
        if hasattr(current_user, "id"):
            return current_user.id
        if isinstance(current_user, dict):
            if "id" in current_user:
                return current_user["id"]
            if "user_id" in current_user:
                return current_user["user_id"]
        raise ErrorResponseAPIException(status_code=500, detail="无法提取当前用户 ID", code=50000)

    async def generate_for_conversation(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        current_user: Any,
    ) -> DailyRecord:
        user_id = self._get_user_id(current_user)

        conv = await self._get_conversation(db, conversation_id)
        if conv.user_id != user_id:
            raise ForbiddenException("无权访问该会话")
        if conv.status != "completing":
            raise ConflictException("会话状态必须为 completing")

        existing_record_id = await self._get_existing_record_id(db, conversation_id)
        if existing_record_id:
            raise ConflictException("该会话已生成日记录")

        messages = await self._get_conversation_messages(db, conversation_id)
        if not messages:
            raise ErrorResponseAPIException(
                status_code=400,
                detail="会话中尚无可用于生成总结的消息",
                code=40002,
            )

        payload = await self._build_payload_from_messages(messages)

        new_record = DailyRecord(
            user_id=user_id,
            conversation_id=conversation_id,
            record_date=conv.record_date,
            body_text=payload["body_text"],
            summary_text=payload["summary_text"],
            emotion_overall_score=payload["emotion_overall_score"],
            keywords=payload["keywords"],
            extra_json=self._build_extra_json(payload, source="conversation_complete", message_count=len(messages)),
        )
        db.add(new_record)

        try:
            await db.flush()

            for event in payload["events"]:
                db.add(
                    RecordEvent(
                        record_id=new_record.id,
                        user_id=user_id,
                        content=event["content"],
                        source="ai",
                    )
                )

            for emotion in payload["emotions"]:
                db.add(
                    RecordEmotion(
                        record_id=new_record.id,
                        user_id=user_id,
                        emotion_label=emotion["emotion_label"],
                        intensity=emotion["intensity"],
                        source="ai",
                    )
                )

            for expense in payload["expenses"]:
                db.add(
                    RecordExpense(
                        record_id=new_record.id,
                        user_id=user_id,
                        amount=expense["amount"],
                        currency=expense.get("currency", "CNY"),
                        category=expense.get("category"),
                        description=expense.get("description"),
                        source="ai",
                    )
                )

            for location in payload["locations"]:
                db.add(
                    RecordLocation(
                        record_id=new_record.id,
                        user_id=user_id,
                        name=location["name"],
                        source="ai",
                    )
                )

            for inspiration in payload["inspirations"]:
                db.add(
                    RecordInspiration(
                        record_id=new_record.id,
                        user_id=user_id,
                        content=inspiration["content"],
                        source="ai",
                    )
                )

            conv.status = "completed"
            conv.updated_at = utc_now()

            await db.commit()
        except Exception as exc:
            await db.rollback()
            raise ErrorResponseAPIException(
                status_code=500,
                detail=f"总结生成结果落库失败：{exc}",
                code=50000,
            ) from exc

        stmt_full = (
            select(DailyRecord)
            .where(DailyRecord.id == new_record.id)
            .options(
                selectinload(DailyRecord.events),
                selectinload(DailyRecord.emotions),
                selectinload(DailyRecord.expenses),
                selectinload(DailyRecord.locations),
                selectinload(DailyRecord.inspirations),
            )
        )
        return (await db.execute(stmt_full)).scalar_one()

    async def build_payload_from_messages(self, messages: list[ConversationMessage]) -> dict[str, Any]:
        return await self._build_payload_from_messages(messages)

    async def build_payload_from_body_text(self, body_text: str) -> dict[str, Any]:
        diary_ai = DiaryAIService()
        if not (settings.TOKENHUB_AUTHORIZATION or settings.TOKENHUB_API_KEY):
            logger.warning("TokenHub credentials are not configured, using local fallback for payload from body_text")
            return diary_ai.build_record_payload_from_body_text_fallback(body_text)

        try:
            return await diary_ai.build_record_payload_from_body_text(body_text)
        except Exception as exc:
            logger.exception("TokenHub build_record_payload_from_body_text failed, using fallback")
            # 如果是业务定义的 ErrorResponseAPIException 则继续向上抛，让全局异常处理捕捉
            if isinstance(exc, ErrorResponseAPIException):
                raise
            # 其他未知异常则使用 fallback 兜底（或也可选择抛出 502）
            return diary_ai.build_record_payload_from_body_text_fallback(body_text)

    async def build_body_text_from_messages(self, messages: list[ConversationMessage]) -> str:
        payload = await self._build_payload_from_messages(messages)
        return payload["body_text"]

    async def _build_payload_from_messages(self, messages: list[ConversationMessage]) -> dict[str, Any]:
        diary_ai = DiaryAIService()
        if not (settings.TOKENHUB_AUTHORIZATION or settings.TOKENHUB_API_KEY):
            logger.warning("TokenHub credentials are not configured, using local fallback for payload from messages")
            return diary_ai.build_record_payload_from_messages_fallback(messages)

        try:
            return await diary_ai.build_record_payload_from_messages(messages)
        except Exception as exc:
            logger.exception("TokenHub build_record_payload_from_messages failed, using fallback")
            if isinstance(exc, ErrorResponseAPIException):
                raise
            return diary_ai.build_record_payload_from_messages_fallback(messages)

    async def _get_conversation(self, db: AsyncSession, conversation_id: uuid.UUID) -> Conversation:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.deleted_at.is_(None),
        )
        conv = (await db.execute(stmt)).scalar_one_or_none()
        if not conv:
            raise NotFoundException("会话不存在")
        return conv

    async def _get_existing_record_id(self, db: AsyncSession, conversation_id: uuid.UUID) -> uuid.UUID | None:
        stmt = select(DailyRecord.id).where(
            DailyRecord.conversation_id == conversation_id,
            DailyRecord.deleted_at.is_(None),
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def _get_conversation_messages(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
    ) -> list[ConversationMessage]:
        stmt = (
            select(ConversationMessage)
            .where(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.deleted_at.is_(None),
            )
            .order_by(asc(ConversationMessage.sequence_number))
        )
        return list((await db.execute(stmt)).scalars().all())

    def _build_extra_json(self, payload: dict[str, Any], *, source: str, message_count: int | None = None) -> dict[str, Any]:
        extra_json: dict[str, Any] = {
            "source": source,
            "provider": "tokenhub",
            "model": settings.TOKENHUB_MODEL,
            "structured_payload": payload,
        }
        if message_count is not None:
            extra_json["message_count"] = message_count
        return extra_json
