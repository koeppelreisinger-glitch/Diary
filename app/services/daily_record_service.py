import uuid
import zoneinfo
from datetime import datetime, date
from sqlalchemy import select, asc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.user_setting import UserSetting
from app.models.conversation import Conversation, ConversationMessage
from app.models.daily_record import DailyRecord, RecordTag
from app.models.base import utc_now
from app.schemas.daily_record import (
    TodayDailyRecordResponse,
    DailyRecordDetailResponse,
    UpdateDailyRecordRequest,
    UpdateDailyRecordBodyRequest,
    SaveSupplementRequest,
    CreateManualRecordRequest,
)
from app.core.exceptions import ErrorResponseAPIException, NotFoundException, ForbiddenException


class DailyRecordService:
    @staticmethod
    def _filter_deleted_children(record: DailyRecord) -> DailyRecord:
        record.events = [item for item in record.events if item.deleted_at is None]
        record.emotions = [item for item in record.emotions if item.deleted_at is None]
        record.expenses = [item for item in record.expenses if item.deleted_at is None]
        record.locations = [item for item in record.locations if item.deleted_at is None]
        record.tags = [item for item in record.tags if item.deleted_at is None]
        return record

    @staticmethod
    async def _get_today_date(session: AsyncSession, user_id: uuid.UUID) -> datetime.date:
        stmt = select(UserSetting).where(UserSetting.user_id == user_id, UserSetting.deleted_at.is_(None))
        setting = (await session.execute(stmt)).scalar_one_or_none()
        if not setting or not setting.timezone:
            raise ErrorResponseAPIException(status_code=500, detail="用户时区配置缺失或非法", code=50002)
        try:
            return datetime.now(zoneinfo.ZoneInfo(setting.timezone)).date()
        except Exception:
            raise ErrorResponseAPIException(status_code=500, detail="用户时区配置非法", code=50002)

    @staticmethod
    async def _load_record_full(session: AsyncSession, record_id: uuid.UUID) -> DailyRecord | None:
        """按 ID 加载带所有子关系的 DailyRecord ORM 对象（包含软删子条目）。"""
        stmt = (
            select(DailyRecord)
            .where(DailyRecord.id == record_id, DailyRecord.deleted_at.is_(None))
            .options(
                selectinload(DailyRecord.events),
                selectinload(DailyRecord.emotions),
                selectinload(DailyRecord.expenses),
                selectinload(DailyRecord.locations),
                selectinload(DailyRecord.tags),
            )
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def _get_record_by_date(session: AsyncSession, user_id: uuid.UUID, target_date: date) -> DailyRecordDetailResponse | None:
        stmt = select(DailyRecord).where(
            DailyRecord.user_id == user_id,
            DailyRecord.record_date == target_date,
            DailyRecord.deleted_at.is_(None)
        ).options(
            selectinload(DailyRecord.events),
            selectinload(DailyRecord.emotions),
            selectinload(DailyRecord.expenses),
            selectinload(DailyRecord.locations),
            selectinload(DailyRecord.tags)
        )
        record = (await session.execute(stmt)).scalar_one_or_none()
        if not record:
            return None

        record = DailyRecordService._filter_deleted_children(record)
        return DailyRecordDetailResponse.model_validate(record)

    @staticmethod
    async def get_today_record(session: AsyncSession, user_id: uuid.UUID) -> TodayDailyRecordResponse:
        today_date = await DailyRecordService._get_today_date(session, user_id)

        conv_stmt = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.record_date == today_date,
            Conversation.deleted_at.is_(None)
        )
        conv = (await session.execute(conv_stmt)).scalar_one_or_none()

        if not conv or conv.status == "recording":
            return TodayDailyRecordResponse(has_record=False, is_generating=False)

        if conv.status == "completing":
            return TodayDailyRecordResponse(has_record=False, is_generating=True)

        record_detail = await DailyRecordService._get_record_by_date(session, user_id, today_date)
        return TodayDailyRecordResponse(
            has_record=True,
            is_generating=False,
            record=record_detail
        )

    @staticmethod
    async def get_record_by_date(session: AsyncSession, user_id: uuid.UUID, record_date: date) -> DailyRecordDetailResponse:
        record_detail = await DailyRecordService._get_record_by_date(session, user_id, record_date)
        if not record_detail:
            raise NotFoundException(detail="该日期无可用记录")
        return record_detail

    @staticmethod
    async def update_record(session: AsyncSession, user_id: uuid.UUID, record_id: uuid.UUID, req: UpdateDailyRecordRequest) -> DailyRecordDetailResponse:
        """轻量标注编辑：仅更新 user_note / keywords / tags，不触发结构化重建。"""
        stmt = select(DailyRecord).where(DailyRecord.id == record_id, DailyRecord.deleted_at.is_(None))
        record = (await session.execute(stmt)).scalar_one_or_none()

        if not record:
            raise NotFoundException("记录不存在")
        if record.user_id != user_id:
            raise ForbiddenException("无权修改该记录")

        updated = False
        data = req.model_dump(exclude_unset=True)

        if "user_note" in data:
            record.user_note = data["user_note"]
            updated = True

        if "keywords" in data:
            record.keywords = data["keywords"] or []
            updated = True

        if "tags_to_add" in data and data["tags_to_add"]:
            normalized_names = []
            for raw_name in data["tags_to_add"]:
                if raw_name is None:
                    continue
                name = raw_name.strip()
                if not name:
                    continue
                normalized_names.append(name)

            normalized_names = list(dict.fromkeys(normalized_names))
            existing_names = {
                t.tag_name for t in record.tags if t.deleted_at is None
            }
            for tag_name in normalized_names:
                if tag_name in existing_names:
                    continue
                new_tag = RecordTag(
                    record_id=record.id,
                    user_id=user_id,
                    tag_name=tag_name,
                    source="user"
                )
                session.add(new_tag)
                updated = True

        if "tags_to_remove" in data and data["tags_to_remove"]:
            rm_stmt = select(RecordTag).where(
                RecordTag.id.in_(data["tags_to_remove"]),
                RecordTag.record_id == record.id,
                RecordTag.user_id == user_id,
                RecordTag.deleted_at.is_(None)
            )
            tags_to_del = (await session.execute(rm_stmt)).scalars().all()
            for t in tags_to_del:
                t.deleted_at = utc_now()
                updated = True

        if updated:
            record.updated_at = utc_now()
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                raise ErrorResponseAPIException(status_code=400, detail="数据约束冲突，请检查标签是否重复", code=40000)

        updated_record = await DailyRecordService._get_record_by_date(session, user_id, record.record_date)
        return updated_record

    @staticmethod
    async def update_body(
        session: AsyncSession,
        user_id: uuid.UUID,
        record_id: uuid.UUID,
        req: UpdateDailyRecordBodyRequest,
    ) -> DailyRecordDetailResponse:
        """
        Path A — 手动改正文：
          鉴权 → 调 DiaryRebuildService.rebuild()（含事务 commit）→ 返回最新详情
        """
        record = await DailyRecordService._load_record_full(session, record_id)
        if not record:
            raise NotFoundException("记录不存在")
        if record.user_id != user_id:
            raise ForbiddenException("无权修改该记录")

        from app.services.diary_rebuild_service import DiaryRebuildService
        rebuild_svc = DiaryRebuildService()
        updated_record = await rebuild_svc.rebuild(session, record, req.body_text)

        updated_record = DailyRecordService._filter_deleted_children(updated_record)
        return DailyRecordDetailResponse.model_validate(updated_record)

    @staticmethod
    async def save_supplement(
        session: AsyncSession,
        user_id: uuid.UUID,
        record_id: uuid.UUID,
        req: SaveSupplementRequest,
    ) -> DailyRecordDetailResponse:
        """
        Path B — 保存本次补充 / AI 重新生成：
          1. 鉴权 + 加载 record（含子关系）
          2. 取出此 record 对应 conversation 的全部消息（含补充部分）
          3a. 若有消息 → 拼合全部 user 消息文本，调 AI 生成 payload → 重建
          3b. 若无消息（如手动补录 / AI 重新生成无新内容）→ 直接用现有 body_text 再次 rebuild
              （prompt 里有风格变化指令，每次结果会有所不同）
          4. 返回最新 DailyRecordDetailResponse
        """
        # 1. 鉴权
        record = await DailyRecordService._load_record_full(session, record_id)
        if not record:
            raise NotFoundException("记录不存在")
        if record.user_id != user_id:
            raise ForbiddenException("无权修改该记录")

        # 2. 从关联会话取出全部已发消息（按序）
        stmt_msgs = (
            select(ConversationMessage)
            .where(
                ConversationMessage.conversation_id == record.conversation_id,
                ConversationMessage.deleted_at.is_(None),
            )
            .order_by(asc(ConversationMessage.sequence_number))
        )
        messages = (await session.execute(stmt_msgs)).scalars().all()

        from app.services.diary_rebuild_service import DiaryRebuildService

        if not messages:
            # 3b. 无消息回落：使用现有正文直接重建（rebuild prompt 含风格变化指令）
            body_src = record.body_text or record.summary_text or ""
            if not body_src.strip():
                raise ErrorResponseAPIException(
                    status_code=400,
                    detail="当前记录没有正文内容，无法进行 AI 重新生成",
                    code=40002,
                )
            updated_record = await DiaryRebuildService().rebuild(session, record, body_src)
        else:
            # 3a. 有消息：基于完整对话生成 payload → 重建
            from app.services.summary_generation_service import SummaryGenerationService
            payload = await SummaryGenerationService().build_payload_from_messages(messages)
            updated_record = await DiaryRebuildService().rebuild_with_payload(session, record, payload)

        # 4. 过滤软删 tags 并序列化返回
        updated_record = DailyRecordService._filter_deleted_children(updated_record)
        return DailyRecordDetailResponse.model_validate(updated_record)

    @staticmethod
    async def create_from_manual_body(
        session: AsyncSession,
        user_id: uuid.UUID,
        req: CreateManualRecordRequest,
    ) -> DailyRecordDetailResponse:
        """
        补录：从正文直接创建日记（适合过往无记录日期手动补录）
          1. 校验该日期无已有记录（避免重复）
          2. 创建 Conversation（status=completed）  
          3. 创建 DailyRecord（仅 body_text 初始化）
          4. 调 DiaryRebuildService.rebuild() 提取结构化数据
          5. 返回最新 DailyRecordDetailResponse
        """
        # 1. 防止重复
        existing_stmt = select(DailyRecord).where(
            DailyRecord.user_id == user_id,
            DailyRecord.record_date == req.record_date,
            DailyRecord.deleted_at.is_(None),
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            raise ErrorResponseAPIException(
                status_code=400,
                detail=f"{req.record_date} 已有记录，请通过编辑正文来修改",
                code=40003,
            )

        # 2. 创建 Conversation
        conv = Conversation(
            user_id=user_id,
            record_date=req.record_date,
            status="completed",
        )
        session.add(conv)
        await session.flush()  # 获取 conv.id

        # 3. 创建占位 DailyRecord（body_text 先写入，rebuild 会覆盖）
        record = DailyRecord(
            user_id=user_id,
            conversation_id=conv.id,
            record_date=req.record_date,
            body_text=req.body_text.strip(),
            summary_text=req.body_text.strip()[:120],
            emotion_overall_score=5,
            keywords=[],
        )
        session.add(record)
        await session.flush()  # 获取 record.id

        # 4. AI 提取结构化数据（rebuild 内含 commit）
        from app.services.diary_rebuild_service import DiaryRebuildService

        # 先 commit 基础数据（rebuild 内部会 commit 一次）
        await session.commit()
        await session.refresh(record)

        updated_record = await DiaryRebuildService().rebuild(session, record, req.body_text.strip())
        updated_record = DailyRecordService._filter_deleted_children(updated_record)
        return DailyRecordDetailResponse.model_validate(updated_record)
