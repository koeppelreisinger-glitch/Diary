import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import ErrorResponseAPIException
from app.models.base import utc_now
from app.models.daily_record import (
    DailyRecord,
    RecordEmotion,
    RecordEvent,
    RecordExpense,
    RecordLocation,
    RecordInspiration,
)
from app.services.summary_generation_service import SummaryGenerationService

logger = logging.getLogger(__name__)


class DiaryRebuildService:
    async def rebuild(
        self,
        db: AsyncSession,
        record: DailyRecord,
        new_body_text: str,
    ) -> DailyRecord:
        """从正文文本重建（Path A）：先调 AI 提取 payload，再应用重建。"""
        logger.info("DiaryRebuildService.rebuild: calling AI to extract payload from body_text, record_id=%s", record.id)
        try:
            payload = await SummaryGenerationService().build_payload_from_body_text(new_body_text)
            await self._apply_rebuild_with_payload(db, record, payload)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.exception("DiaryRebuildService.rebuild failed and rolled back, record_id=%s", record.id)
            if isinstance(exc, ErrorResponseAPIException):
                raise
            raise ErrorResponseAPIException(
                status_code=500,
                detail=f"日记正文重建失败：{exc}",
                code=50000,
            ) from exc

        logger.info("DiaryRebuildService.rebuild succeeded, record_id=%s", record.id)
        return await self._get_record_full(db, record.id)

    async def rebuild_with_payload(
        self,
        db: AsyncSession,
        record: DailyRecord,
        payload: dict[str, Any],
    ) -> DailyRecord:
        """直接使用已有 payload 重建（Path B）：避免重复调 AI。"""
        logger.info("DiaryRebuildService.rebuild_with_payload: applying pre-built payload, record_id=%s", record.id)
        try:
            await self._apply_rebuild_with_payload(db, record, payload)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.exception("DiaryRebuildService.rebuild_with_payload failed and rolled back, record_id=%s", record.id)
            if isinstance(exc, ErrorResponseAPIException):
                raise
            raise ErrorResponseAPIException(
                status_code=500,
                detail=f"日记补充重建失败：{exc}",
                code=50000,
            ) from exc

        logger.info("DiaryRebuildService.rebuild_with_payload succeeded, record_id=%s", record.id)
        return await self._get_record_full(db, record.id)

    async def _get_record_full(self, db: AsyncSession, record_id: uuid.UUID) -> DailyRecord:
        stmt = (
            select(DailyRecord)
            .where(DailyRecord.id == record_id)
            .options(
                selectinload(DailyRecord.events),
                selectinload(DailyRecord.emotions),
                selectinload(DailyRecord.expenses),
                selectinload(DailyRecord.locations),
                selectinload(DailyRecord.inspirations),
            )
        )
        return (await db.execute(stmt)).scalar_one()

    async def _apply_rebuild_with_payload(
        self,
        db: AsyncSession,
        record: DailyRecord,
        payload: dict[str, Any],
    ) -> None:
        now = utc_now()

        record.body_text = payload["body_text"]
        record.summary_text = payload["summary_text"]
        record.emotion_overall_score = payload["emotion_overall_score"]
        record.keywords = payload["keywords"]
        record.extra_json = {
            "source": "body_rebuild",
            "provider": "tokenhub",
            "model": settings.TOKENHUB_MODEL,
            "structured_payload": payload,
        }
        record.updated_at = now

        await db.refresh(record, ["events", "emotions", "expenses", "locations", "inspirations"])

        for event in record.events:
            if event.deleted_at is None:
                event.deleted_at = now

        for emotion in record.emotions:
            if emotion.deleted_at is None:
                emotion.deleted_at = now

        for expense in record.expenses:
            if expense.deleted_at is None:
                expense.deleted_at = now

        for location in record.locations:
            if location.deleted_at is None:
                location.deleted_at = now

        for inspiration in record.inspirations:
            if inspiration.deleted_at is None:
                inspiration.deleted_at = now

        await db.flush()

        record_id = record.id
        user_id = record.user_id

        for event in payload["events"]:
            db.add(
                RecordEvent(
                    record_id=record_id,
                    user_id=user_id,
                    content=event["content"],
                    source="ai",
                )
            )

        for emotion in payload["emotions"]:
            db.add(
                RecordEmotion(
                    record_id=record_id,
                    user_id=user_id,
                    emotion_label=emotion["emotion_label"],
                    intensity=emotion["intensity"],
                    source="ai",
                )
            )

        for expense in payload["expenses"]:
            db.add(
                RecordExpense(
                    record_id=record_id,
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
                    record_id=record_id,
                    user_id=user_id,
                    name=location["name"],
                    source="ai",
                )
            )

        for inspiration in payload["inspirations"]:
            db.add(
                RecordInspiration(
                    record_id=record_id,
                    user_id=user_id,
                    content=inspiration["content"],
                    source="ai",
                )
            )
