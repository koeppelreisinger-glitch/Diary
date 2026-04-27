import uuid
from typing import Any
import zoneinfo
import logging
from datetime import datetime
from sqlalchemy import select, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import asyncio

from app.models.conversation import Conversation, ConversationMessage
from app.models.user_setting import UserSetting
from app.models.base import utc_now
from app.schemas.conversation import (
    TodayConversationResponse,
    ConversationResponse,
    CreateConversationResponse,
    MessageListResponse,
    ConversationMessageResponse,
    SendMessageRequest,
    SendMessageResponse,
    CompleteConversationResponse,
)
from app.core.config import settings
from app.core.exceptions import ErrorResponseAPIException, NotFoundException, ForbiddenException, ConflictException

logger = logging.getLogger(__name__)

async def run_background_summary(conversation_id: uuid.UUID, user_id: uuid.UUID):
    """后台异步执行总结生成，确保主线程快速返回"""
    from app.core.database import AsyncSessionLocal
    from app.services.summary_generation_service import SummaryGenerationService
    async with AsyncSessionLocal() as db:
        try:
            summary_svc = SummaryGenerationService()
            await summary_svc.generate_for_conversation(db, conversation_id, {"id": user_id})
        except Exception as e:
            logger.exception(f"Background summary generation failed: {e}")

class ConversationService:
    @staticmethod
    async def _get_today_date(session: AsyncSession, user_id: uuid.UUID) -> datetime.date:
        stmt = select(UserSetting).where(UserSetting.user_id == user_id, UserSetting.deleted_at.is_(None))
        stmt = stmt.order_by(desc(UserSetting.updated_at), desc(UserSetting.created_at)).limit(1)
        result = await session.execute(stmt)
        setting = result.scalars().first()

        tz_str = (setting.timezone if setting and setting.timezone else None) or "Asia/Shanghai"

        try:
            tz = zoneinfo.ZoneInfo(tz_str)
            return datetime.now(tz).date()
        except Exception:
            return datetime.now(zoneinfo.ZoneInfo("Asia/Shanghai")).date()

    @staticmethod
    async def get_today_conversation(session: AsyncSession, user_id: uuid.UUID) -> TodayConversationResponse:
        today_date = await ConversationService._get_today_date(session, user_id)

        stmt = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.record_date == today_date,
            Conversation.deleted_at.is_(None)
        ).order_by(desc(Conversation.updated_at), desc(Conversation.created_at)).limit(1)
        result = await session.execute(stmt)
        conv = result.scalars().first()

        if not conv:
            return TodayConversationResponse(has_today=False, conversation=None)

        msg_count_stmt = select(func.count(ConversationMessage.id)).where(
            ConversationMessage.conversation_id == conv.id,
            ConversationMessage.role != "system",
            ConversationMessage.deleted_at.is_(None)
        )
        msg_count = (await session.execute(msg_count_stmt)).scalar() or 0

        return TodayConversationResponse(
            has_today=True,
            conversation=ConversationResponse(
                id=conv.id,
                status=conv.status,
                record_date=conv.record_date,
                message_count=msg_count,
                created_at=conv.created_at,
                updated_at=conv.updated_at
            )
        )

    @staticmethod
    async def create_today_conversation(session: AsyncSession, user_id: uuid.UUID) -> CreateConversationResponse:
        try:
            today_date = await ConversationService._get_today_date(session, user_id)

            # 1. 优先检查今日是否已有会话
            stmt_check = select(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.record_date == today_date,
                Conversation.deleted_at.is_(None)
            ).order_by(desc(Conversation.updated_at), desc(Conversation.created_at)).limit(1)
            existing_conv = (await session.execute(stmt_check)).scalars().first()
            if existing_conv:
                return CreateConversationResponse(
                    id=existing_conv.id,
                    status=existing_conv.status,
                    record_date=existing_conv.record_date,
                    created_at=existing_conv.created_at
                )

            # 2. 正常创建逻辑
            new_id = uuid.uuid4()
            new_conv = Conversation(
                id=new_id,
                user_id=user_id,
                record_date=today_date,
                status="recording"
            )
            session.add(new_conv)

            # ── 预加载指令 ──────────────────────────────────────────────────
            system_msg = ConversationMessage(
                conversation_id=new_id,
                role="system",
                content_type="text",
                content=settings.TOKENHUB_CHAT_SYSTEM_PROMPT,
                sequence_number=0
            )
            session.add(system_msg)

            await session.commit()
            
            # 返回时手动构造响应，避免 refresh 可能带来的状态不一致
            return CreateConversationResponse(
                id=new_id,
                status="recording",
                record_date=today_date,
                created_at=utc_now()  # 近似值，保证符合 schema
            )
        except IntegrityError:
            await session.rollback()
            # 并发情况下再次查询
            stmt_check = select(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.record_date == today_date,
                Conversation.deleted_at.is_(None)
            )
            existing_conv = (await session.execute(stmt_check)).scalar_one()
            return CreateConversationResponse(
                id=existing_conv.id,
                status=existing_conv.status,
                record_date=existing_conv.record_date,
                created_at=existing_conv.created_at
            )
        except Exception as e:
            logger.exception(f"create_today_conversation failed: {e}")
            raise ErrorResponseAPIException(status_code=500, detail=f"内部错误: {str(e)}", code=50001)

    @staticmethod
    async def _get_conversation_secured(session: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.deleted_at.is_(None)
        )
        result = await session.execute(stmt)
        conv = result.scalar_one_or_none()

        if not conv:
            raise NotFoundException(detail="会话不存在")
        if conv.user_id != user_id:
            raise ForbiddenException(detail="该会话不属于当前用户")

        return conv

    @staticmethod
    async def get_messages(session: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID, limit: int = 50, before_sequence: int | None = None) -> MessageListResponse:
        await ConversationService._get_conversation_secured(session, conversation_id, user_id)

        total_stmt = select(func.count(ConversationMessage.id)).where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.role != "system",
            ConversationMessage.deleted_at.is_(None)
        )
        total_count = (await session.execute(total_stmt)).scalar() or 0

        stmt = select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.role != "system",
            ConversationMessage.deleted_at.is_(None)
        )
        if before_sequence is not None:
            stmt = stmt.where(ConversationMessage.sequence_number < before_sequence)

        stmt = stmt.order_by(desc(ConversationMessage.sequence_number)).limit(limit)
        result = await session.execute(stmt)
        messages_desc = result.scalars().all()

        messages_asc = list(reversed(messages_desc))

        return MessageListResponse(
            conversation_id=conversation_id,
            total_count=total_count,
            messages=[ConversationMessageResponse.model_validate(m) for m in messages_asc]
        )

    @staticmethod
    async def send_message(session: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID, request: SendMessageRequest) -> SendMessageResponse:
        conv = await ConversationService._get_conversation_secured(session, conversation_id, user_id)

        # ── Phase 2 状态校验逻辑 ────────────────────────────────────────
        # completing 状态：一律禁止（无论是否 is_supplement）
        if conv.status == "completing":
            raise ErrorResponseAPIException(
                status_code=409,
                detail="会话正在生成总结中，请稍后再发",
                code=40902
            )

        # completed 状态：
        #   - is_supplement=True  → 允许（Phase 2 补写通道）
        #   - is_supplement=False → 禁止（原有行为）
        if conv.status == "completed" and not request.is_supplement:
            raise ErrorResponseAPIException(
                status_code=409,
                detail="今日记录已结束，如需补充请将 is_supplement 置为 true",
                code=40903
            )
        # ────────────────────────────────────────────────────────────────

        if request.content_type == "text" and not request.content:
            raise ErrorResponseAPIException(status_code=400, detail="文本消息内容不能为空", code=40001)

        if request.content_type == "voice" and not request.media_file_id:
            raise ErrorResponseAPIException(status_code=400, detail="语音消息缺失媒体文件ID", code=40003)

        # 获取当前最大的 sequence_number
        max_seq_stmt = select(func.max(ConversationMessage.sequence_number)).where(
            ConversationMessage.conversation_id == conversation_id
        )
        max_seq = (await session.execute(max_seq_stmt)).scalar() or 0

        user_seq = max_seq + 1
        user_msg = ConversationMessage(
            conversation_id=conversation_id,
            role="user",
            content_type=request.content_type,
            content=request.content or "（语音转写等占位）",
            media_file_id=request.media_file_id,
            image_url=request.image_url,
            sequence_number=user_seq
        )
        session.add(user_msg)

        try:
            await session.commit()
            await session.refresh(user_msg)
        except IntegrityError:
            await session.rollback()
            raise ErrorResponseAPIException(status_code=500, detail="并发消息序号分配冲突", code=50000)

        # 取出该会话所有消息（包含已预加载的 system 消息）送给 AI 伙伴
        stmt_all_msgs = select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.deleted_at.is_(None)
        ).order_by(asc(ConversationMessage.sequence_number))
        all_messages = (await session.execute(stmt_all_msgs)).scalars().all()

        from app.services.ai_companion_service import AICompanionService
        ai_reply_text = await AICompanionService().generate_reply(all_messages, mode=request.mode)

        ai_seq = user_seq + 1
        ai_msg = ConversationMessage(
            conversation_id=conversation_id,
            role="ai",
            content_type="text",
            content=ai_reply_text,
            sequence_number=ai_seq
        )
        session.add(ai_msg)

        try:
            await session.commit()
            await session.refresh(ai_msg)
        except IntegrityError:
            await session.rollback()
            raise ErrorResponseAPIException(status_code=500, detail="并发消息序号分配冲突", code=50000)

        return SendMessageResponse(
            user_message=ConversationMessageResponse.model_validate(user_msg),
            ai_message=ConversationMessageResponse.model_validate(ai_msg)
        )

    @staticmethod
    async def complete_conversation(session: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> CompleteConversationResponse:
        conv = await ConversationService._get_conversation_secured(session, conversation_id, user_id)

        if conv.status in ("completing", "completed"):
            raise ErrorResponseAPIException(status_code=409, detail="会话已处于结束状态", code=40903)

        conv.status = "completing"
        conv.updated_at = utc_now()

        try:
            await session.commit()
            await session.refresh(conv)
        except Exception:
            await session.rollback()
            raise

        logger.info(f"Triggered summary generation for conversation_id: {conversation_id}")

        # 立即调用同步生成总结
        from app.services.summary_generation_service import SummaryGenerationService
        summary_svc = SummaryGenerationService()
        record = await summary_svc.generate_for_conversation(session, conversation_id, {"id": user_id})

        return CompleteConversationResponse(
            conversation_id=conv.id,
            status=conv.status,
            updated_at=conv.updated_at,
            daily_record=record
        )

    @staticmethod
    async def complete_conversation_and_trigger_background(
        session: AsyncSession, 
        conversation_id: uuid.UUID, 
        user_id: uuid.UUID,
        background_tasks: Any
    ) -> CompleteConversationResponse:
        """异步版本：仅更新状态为 completing，将生成任务转入后台"""
        conv = await ConversationService._get_conversation_secured(session, conversation_id, user_id)
 
        if conv.status in ("completing", "completed"):
            raise ErrorResponseAPIException(status_code=409, detail="会话已处于结束状态", code=40903)
 
        conv.status = "completing"
        conv.updated_at = utc_now()
 
        try:
            await session.commit()
            await session.refresh(conv)
        except Exception:
            await session.rollback()
            raise
 
        logger.info(f"Triggered background summary generation for conversation_id: {conversation_id}")
 
        # 挂载后台任务
        background_tasks.add_task(run_background_summary, conversation_id, user_id)
 
        return CompleteConversationResponse(
            conversation_id=conv.id,
            status=conv.status,
            updated_at=conv.updated_at,
            daily_record=None  # 后台生成，初始返回空
        )
