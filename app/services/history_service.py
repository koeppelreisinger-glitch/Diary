import uuid
import calendar
from datetime import date
from math import ceil
from typing import Optional, List, Dict

from sqlalchemy import select, func, desc, or_, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.daily_record import DailyRecord, RecordEvent, RecordInspiration, RecordEmotion, RecordLocation, RecordExpense
from app.schemas.daily_record import DailyRecordDetailResponse
from app.schemas.history import (
    HistoryListResponse,
    HistoryRecordItemResponse,
    HistoryCalendarResponse,
    HistoryCalendarDayItemResponse,
    HistoryTimelineResponse,
    HistoryTimelineGroupResponse,
    HistoryTimelineItemResponse,
    HistoryEventItemResponse,
    HistoryEventListResponse,
    HistoryInspirationItemResponse,
    HistoryInspirationListResponse,
    HistoryEmotionItemResponse,
    HistoryEmotionListResponse,
    HistoryLocationItemResponse,
    HistoryLocationListResponse,
    HistoryExpenseItemResponse,
    HistoryExpenseListResponse,
)
from app.core.exceptions import ErrorResponseAPIException, NotFoundException


class HistoryService:

    # ──────────────────────────────────────────────
    # 内部工具方法
    # ──────────────────────────────────────────────

    @staticmethod
    def _build_summary_preview(text: Optional[str], max_length: int = 50) -> str:
        """统一的预览文本生成方法，安全处理 None 与空字符串"""
        if not text:
            return ""
        return text[:max_length] + "..." if len(text) > max_length else text

    # ──────────────────────────────────────────────
    # 历史记录列表
    # ──────────────────────────────────────────────

    @staticmethod
    async def list_daily_records(
        session: AsyncSession,
        user_id: uuid.UUID,
        page: int,
        page_size: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        keyword: Optional[str] = None,
        inspiration: Optional[str] = None,
        min_emotion_score: Optional[int] = None,
        max_emotion_score: Optional[int] = None
    ) -> HistoryListResponse:
        # 参数交叉校验
        if start_date and end_date and start_date > end_date:
            raise ErrorResponseAPIException(status_code=400, detail="start_date 不能晚于 end_date", code=40001)
        if min_emotion_score is not None and max_emotion_score is not None and min_emotion_score > max_emotion_score:
            raise ErrorResponseAPIException(status_code=400, detail="min_emotion_score 不能大于 max_emotion_score", code=40001)

        filters = [
            DailyRecord.user_id == user_id,
            DailyRecord.deleted_at.is_(None)
        ]

        if start_date:
            filters.append(DailyRecord.record_date >= start_date)
        if end_date:
            filters.append(DailyRecord.record_date <= end_date)
        if min_emotion_score is not None:
            filters.append(DailyRecord.emotion_overall_score >= min_emotion_score)
        if max_emotion_score is not None:
            filters.append(DailyRecord.emotion_overall_score <= max_emotion_score)
        if keyword and keyword.strip():
            keyword_like = f"%{keyword.strip()}%"
            filters.append(or_(
                DailyRecord.summary_text.ilike(keyword_like),
                DailyRecord.body_text.ilike(keyword_like),
                DailyRecord.user_note.ilike(keyword_like),
                DailyRecord.keywords.cast(String).ilike(keyword_like),
                DailyRecord.events.any(
                    (RecordEvent.content.ilike(keyword_like)) & (RecordEvent.deleted_at.is_(None))
                ),
                DailyRecord.inspirations.any(
                    (RecordInspiration.content.ilike(keyword_like)) & (RecordInspiration.deleted_at.is_(None))
                ),
                DailyRecord.locations.any(
                    (RecordLocation.name.ilike(keyword_like)) & (RecordLocation.deleted_at.is_(None))
                ),
                DailyRecord.expenses.any(
                    (
                        RecordExpense.description.ilike(keyword_like)
                        | RecordExpense.category.ilike(keyword_like)
                    ) & (RecordExpense.deleted_at.is_(None))
                ),
            ))

        # inspiration 筛选：strip + 空字符串跳过
        if inspiration:
            inspiration = inspiration.strip()
        if inspiration:
            filters.append(
                DailyRecord.inspirations.any(
                    (RecordInspiration.content.ilike(f"%{inspiration}%")) & (RecordInspiration.deleted_at.is_(None))
                )
            )

        count_stmt = select(func.count(DailyRecord.id)).where(*filters)
        total_count = (await session.execute(count_stmt)).scalar_one()

        if total_count == 0:
            return HistoryListResponse(
                total_count=0, total_pages=0,
                current_page=page, page_size=page_size, records=[]
            )

        total_pages = ceil(total_count / page_size)
        offset = (page - 1) * page_size

        stmt = select(
            DailyRecord.id,
            DailyRecord.record_date,
            DailyRecord.body_text,
            DailyRecord.summary_text,
            DailyRecord.emotion_overall_score,
            DailyRecord.keywords,
            DailyRecord.created_at,
            DailyRecord.updated_at
        ).where(*filters).order_by(desc(DailyRecord.record_date)).offset(offset).limit(page_size)

        result = await session.execute(stmt)
        records_db = result.all()

        records = [
            HistoryRecordItemResponse(
                id=r.id,
                record_date=r.record_date,
                body_text=r.body_text or None,
                summary_text=r.summary_text or "",
                emotion_overall_score=r.emotion_overall_score,
                keywords=r.keywords or [],
                created_at=r.created_at,
                updated_at=r.updated_at
            ) for r in records_db
        ]

        return HistoryListResponse(
            total_count=total_count, total_pages=total_pages,
            current_page=page, page_size=page_size, records=records
        )

    # ──────────────────────────────────────────────
    # 指定日期详情
    # ──────────────────────────────────────────────

    @staticmethod
    async def get_daily_record_detail_by_date(
        session: AsyncSession, user_id: uuid.UUID, record_date: date
    ) -> DailyRecordDetailResponse:
        stmt = (
            select(DailyRecord)
            .where(
                DailyRecord.user_id == user_id,
                DailyRecord.record_date == record_date,
                DailyRecord.deleted_at.is_(None)
            )
            .options(
                selectinload(DailyRecord.events),
                selectinload(DailyRecord.emotions),
                selectinload(DailyRecord.expenses),
                selectinload(DailyRecord.locations),
                selectinload(DailyRecord.inspirations),
            )
        )
        record = (await session.execute(stmt)).scalar_one_or_none()
        if not record:
            raise NotFoundException(detail="未找到该日记录或已被删除")
        return DailyRecordDetailResponse.model_validate(record)

    # ──────────────────────────────────────────────
    # 日历视图
    # ──────────────────────────────────────────────

    @staticmethod
    async def get_calendar_view(
        session: AsyncSession, user_id: uuid.UUID, year: int, month: int
    ) -> HistoryCalendarResponse:
        _, last_day = calendar.monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)

        stmt = select(
            DailyRecord.record_date,
            DailyRecord.summary_text,
            DailyRecord.emotion_overall_score,
            DailyRecord.keywords
        ).where(
            DailyRecord.user_id == user_id,
            DailyRecord.deleted_at.is_(None),
            DailyRecord.record_date >= start_date,
            DailyRecord.record_date <= end_date
        ).order_by(DailyRecord.record_date)

        records = (await session.execute(stmt)).all()

        days = [
            HistoryCalendarDayItemResponse(
                record_date=r.record_date,
                has_record=True,
                emotion_overall_score=r.emotion_overall_score,
                keywords=r.keywords or [],
                summary_preview=HistoryService._build_summary_preview(r.summary_text)
            )
            for r in records
        ]

        return HistoryCalendarResponse(year=year, month=month, days=days)

    # ──────────────────────────────────────────────
    # 时间轴视图
    # ──────────────────────────────────────────────

    @staticmethod
    async def get_timeline_view(
        session: AsyncSession, user_id: uuid.UUID,
        start_date: date, end_date: date, limit: int = 100
    ) -> HistoryTimelineResponse:
        if start_date > end_date:
            raise ErrorResponseAPIException(status_code=400, detail="start_date 不能晚于 end_date", code=40001)

        stmt = select(
            DailyRecord.id,
            DailyRecord.record_date,
            DailyRecord.summary_text,
            DailyRecord.emotion_overall_score,
            DailyRecord.keywords
        ).where(
            DailyRecord.user_id == user_id,
            DailyRecord.deleted_at.is_(None),
            DailyRecord.record_date >= start_date,
            DailyRecord.record_date <= end_date
        ).order_by(desc(DailyRecord.record_date)).limit(limit)

        records = (await session.execute(stmt)).all()

        groups_dict: Dict[str, List[HistoryTimelineItemResponse]] = {}
        for r in records:
            ym = r.record_date.strftime("%Y-%m")
            item = HistoryTimelineItemResponse(
                id=r.id,
                record_date=r.record_date,
                summary_preview=HistoryService._build_summary_preview(r.summary_text),
                emotion_overall_score=r.emotion_overall_score,
                keywords=r.keywords or []
            )
            groups_dict.setdefault(ym, []).append(item)

        groups = [
            HistoryTimelineGroupResponse(year_month=ym, items=items)
            for ym, items in groups_dict.items()
        ]

        return HistoryTimelineResponse(groups=groups)

    # ──────────────────────────────────────────────
    # 五表主视图 — events
    # ──────────────────────────────────────────────

    @staticmethod
    async def list_events(
        session: AsyncSession,
        user_id: uuid.UUID,
        page: int,
        page_size: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        keyword: Optional[str] = None,
    ) -> HistoryEventListResponse:
        if start_date and end_date and start_date > end_date:
            raise ErrorResponseAPIException(status_code=400, detail="start_date 不能晚于 end_date", code=40001)

        # 构造过滤条件：通过子表 user_id 绑定用户，join 主表过滤主表软删除
        filters = [
            RecordEvent.user_id == user_id,
            RecordEvent.deleted_at.is_(None),
            DailyRecord.deleted_at.is_(None),
        ]

        if start_date:
            filters.append(DailyRecord.record_date >= start_date)
        if end_date:
            filters.append(DailyRecord.record_date <= end_date)
        if keyword:
            filters.append(RecordEvent.content.ilike(f"%{keyword}%"))

        # join 主表获取 record_date
        join_stmt = select(func.count(RecordEvent.id)).join(
            DailyRecord, RecordEvent.record_id == DailyRecord.id
        ).where(*filters)
        total_count = (await session.execute(join_stmt)).scalar_one()

        if total_count == 0:
            return HistoryEventListResponse(
                total_count=0, total_pages=0,
                current_page=page, page_size=page_size, records=[]
            )

        total_pages = ceil(total_count / page_size)
        offset = (page - 1) * page_size

        stmt = select(
            RecordEvent.id,
            RecordEvent.record_id.label("daily_record_id"),
            DailyRecord.record_date,
            RecordEvent.content,
            RecordEvent.source,
            RecordEvent.is_user_confirmed,
            RecordEvent.created_at,
        ).join(
            DailyRecord, RecordEvent.record_id == DailyRecord.id
        ).where(*filters).order_by(
            desc(DailyRecord.record_date), desc(RecordEvent.created_at)
        ).offset(offset).limit(page_size)

        rows = (await session.execute(stmt)).all()

        records = [
            HistoryEventItemResponse(
                id=r.id,
                daily_record_id=r.daily_record_id,
                record_date=r.record_date,
                content=r.content,
                source=r.source,
                is_user_confirmed=r.is_user_confirmed,
                created_at=r.created_at,
            )
            for r in rows
        ]

        return HistoryEventListResponse(
            total_count=total_count, total_pages=total_pages,
            current_page=page, page_size=page_size, records=records
        )

    # ──────────────────────────────────────────────
    # 五表主视图 — tags
    # ──────────────────────────────────────────────

    @staticmethod
    async def list_inspirations(
        session: AsyncSession,
        user_id: uuid.UUID,
        page: int,
        page_size: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        keyword: Optional[str] = None,
    ) -> HistoryInspirationListResponse:
        if start_date and end_date and start_date > end_date:
            raise ErrorResponseAPIException(status_code=400, detail="start_date 不能晚于 end_date", code=40001)

        if keyword:
            keyword = keyword.strip() or None

        filters = [
            RecordInspiration.user_id == user_id,
            RecordInspiration.deleted_at.is_(None),
            DailyRecord.deleted_at.is_(None),
        ]

        if start_date:
            filters.append(DailyRecord.record_date >= start_date)
        if end_date:
            filters.append(DailyRecord.record_date <= end_date)
        if keyword:
            filters.append(RecordInspiration.content.ilike(f"%{keyword}%"))

        count_stmt = select(func.count(RecordInspiration.id)).join(
            DailyRecord, RecordInspiration.record_id == DailyRecord.id
        ).where(*filters)
        total_count = (await session.execute(count_stmt)).scalar_one()

        if total_count == 0:
            return HistoryInspirationListResponse(
                total_count=0, total_pages=0,
                current_page=page, page_size=page_size, records=[]
            )

        total_pages = ceil(total_count / page_size)
        offset = (page - 1) * page_size

        stmt = select(
            RecordInspiration.id,
            RecordInspiration.record_id.label("daily_record_id"),
            DailyRecord.record_date,
            RecordInspiration.content,
            RecordInspiration.source,
            RecordInspiration.created_at,
        ).join(
            DailyRecord, RecordInspiration.record_id == DailyRecord.id
        ).where(*filters).order_by(
            desc(DailyRecord.record_date), desc(RecordInspiration.created_at)
        ).offset(offset).limit(page_size)

        rows = (await session.execute(stmt)).all()

        records = [
            HistoryInspirationItemResponse(
                id=r.id,
                daily_record_id=r.daily_record_id,
                record_date=r.record_date,
                content=r.content,
                source=r.source,
                created_at=r.created_at,
            )
            for r in rows
        ]

        return HistoryInspirationListResponse(
            total_count=total_count, total_pages=total_pages,
            current_page=page, page_size=page_size, records=records
        )

    # ──────────────────────────────────────────────
    # 五表主视图 — emotions
    # ──────────────────────────────────────────────

    @staticmethod
    async def list_emotions(
        session: AsyncSession,
        user_id: uuid.UUID,
        page: int,
        page_size: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        emotion_label: Optional[str] = None,
        min_intensity: Optional[int] = None,
        max_intensity: Optional[int] = None,
    ) -> HistoryEmotionListResponse:
        if start_date and end_date and start_date > end_date:
            raise ErrorResponseAPIException(status_code=400, detail="start_date 不能晚于 end_date", code=40001)
        if min_intensity is not None and max_intensity is not None and min_intensity > max_intensity:
            raise ErrorResponseAPIException(status_code=400, detail="min_intensity 不能大于 max_intensity", code=40001)

        # emotion_label 清洗
        if emotion_label:
            emotion_label = emotion_label.strip() or None

        filters = [
            RecordEmotion.user_id == user_id,
            RecordEmotion.deleted_at.is_(None),
            DailyRecord.deleted_at.is_(None),
        ]

        if start_date:
            filters.append(DailyRecord.record_date >= start_date)
        if end_date:
            filters.append(DailyRecord.record_date <= end_date)
        if emotion_label:
            filters.append(RecordEmotion.emotion_label == emotion_label)
        if min_intensity is not None:
            filters.append(RecordEmotion.intensity >= min_intensity)
        if max_intensity is not None:
            filters.append(RecordEmotion.intensity <= max_intensity)

        count_stmt = select(func.count(RecordEmotion.id)).join(
            DailyRecord, RecordEmotion.record_id == DailyRecord.id
        ).where(*filters)
        total_count = (await session.execute(count_stmt)).scalar_one()

        if total_count == 0:
            return HistoryEmotionListResponse(
                total_count=0, total_pages=0,
                current_page=page, page_size=page_size, records=[]
            )

        total_pages = ceil(total_count / page_size)
        offset = (page - 1) * page_size

        stmt = select(
            RecordEmotion.id,
            RecordEmotion.record_id.label("daily_record_id"),
            DailyRecord.record_date,
            RecordEmotion.emotion_label,
            RecordEmotion.intensity,
            RecordEmotion.source,
            RecordEmotion.is_user_confirmed,
            RecordEmotion.created_at,
        ).join(
            DailyRecord, RecordEmotion.record_id == DailyRecord.id
        ).where(*filters).order_by(
            desc(DailyRecord.record_date), desc(RecordEmotion.created_at)
        ).offset(offset).limit(page_size)

        rows = (await session.execute(stmt)).all()

        records = [
            HistoryEmotionItemResponse(
                id=r.id,
                daily_record_id=r.daily_record_id,
                record_date=r.record_date,
                emotion_label=r.emotion_label,
                intensity=r.intensity,
                source=r.source,
                is_user_confirmed=r.is_user_confirmed,
                created_at=r.created_at,
            )
            for r in rows
        ]

        return HistoryEmotionListResponse(
            total_count=total_count, total_pages=total_pages,
            current_page=page, page_size=page_size, records=records
        )

    # ──────────────────────────────────────────────
    # 五表主视图 — locations
    # ──────────────────────────────────────────────

    @staticmethod
    async def list_locations(
        session: AsyncSession,
        user_id: uuid.UUID,
        page: int,
        page_size: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        name: Optional[str] = None,
    ) -> HistoryLocationListResponse:
        if start_date and end_date and start_date > end_date:
            raise ErrorResponseAPIException(status_code=400, detail="start_date 不能晚于 end_date", code=40001)

        # name 清洗：strip + 空字符串按未传处理
        if name:
            name = name.strip() or None

        filters = [
            RecordLocation.user_id == user_id,
            RecordLocation.deleted_at.is_(None),
            DailyRecord.deleted_at.is_(None),
        ]

        if start_date:
            filters.append(DailyRecord.record_date >= start_date)
        if end_date:
            filters.append(DailyRecord.record_date <= end_date)
        if name:
            filters.append(RecordLocation.name.ilike(f"%{name}%"))

        count_stmt = select(func.count(RecordLocation.id)).join(
            DailyRecord, RecordLocation.record_id == DailyRecord.id
        ).where(*filters)
        total_count = (await session.execute(count_stmt)).scalar_one()

        if total_count == 0:
            return HistoryLocationListResponse(
                total_count=0, total_pages=0,
                current_page=page, page_size=page_size, records=[]
            )

        total_pages = ceil(total_count / page_size)
        offset = (page - 1) * page_size

        stmt = select(
            RecordLocation.id,
            RecordLocation.record_id.label("daily_record_id"),
            DailyRecord.record_date,
            RecordLocation.name,
            RecordLocation.source,
            RecordLocation.is_user_confirmed,
            RecordLocation.created_at,
        ).join(
            DailyRecord, RecordLocation.record_id == DailyRecord.id
        ).where(*filters).order_by(
            desc(DailyRecord.record_date), desc(RecordLocation.created_at)
        ).offset(offset).limit(page_size)

        rows = (await session.execute(stmt)).all()

        records = [
            HistoryLocationItemResponse(
                id=r.id,
                daily_record_id=r.daily_record_id,
                record_date=r.record_date,
                name=r.name,
                source=r.source,
                is_user_confirmed=r.is_user_confirmed,
                created_at=r.created_at,
            )
            for r in rows
        ]

        return HistoryLocationListResponse(
            total_count=total_count, total_pages=total_pages,
            current_page=page, page_size=page_size, records=records
        )

    # ──────────────────────────────────────────────
    # 五表主视图 — expenses
    # ──────────────────────────────────────────────

    @staticmethod
    async def list_expenses(
        session: AsyncSession,
        user_id: uuid.UUID,
        page: int,
        page_size: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category: Optional[str] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
    ) -> HistoryExpenseListResponse:
        if start_date and end_date and start_date > end_date:
            raise ErrorResponseAPIException(status_code=400, detail="start_date 不能晚于 end_date", code=40001)
        if min_amount is not None and max_amount is not None and min_amount > max_amount:
            raise ErrorResponseAPIException(status_code=400, detail="min_amount 不能大于 max_amount", code=40001)

        # category 清洗：strip + 空字符串按未传处理
        if category:
            category = category.strip() or None

        filters = [
            RecordExpense.user_id == user_id,
            RecordExpense.deleted_at.is_(None),
            DailyRecord.deleted_at.is_(None),
        ]

        if start_date:
            filters.append(DailyRecord.record_date >= start_date)
        if end_date:
            filters.append(DailyRecord.record_date <= end_date)
        if category:
            filters.append(RecordExpense.category == category)
        if min_amount is not None:
            filters.append(RecordExpense.amount >= min_amount)
        if max_amount is not None:
            filters.append(RecordExpense.amount <= max_amount)

        count_stmt = select(func.count(RecordExpense.id)).join(
            DailyRecord, RecordExpense.record_id == DailyRecord.id
        ).where(*filters)
        total_count = (await session.execute(count_stmt)).scalar_one()

        if total_count == 0:
            return HistoryExpenseListResponse(
                total_count=0, total_pages=0,
                current_page=page, page_size=page_size, records=[]
            )

        total_pages = ceil(total_count / page_size)
        offset = (page - 1) * page_size

        stmt = select(
            RecordExpense.id,
            RecordExpense.record_id.label("daily_record_id"),
            DailyRecord.record_date,
            RecordExpense.amount,
            RecordExpense.currency,
            RecordExpense.category,
            RecordExpense.description,
            RecordExpense.source,
            RecordExpense.is_user_confirmed,
            RecordExpense.created_at,
        ).join(
            DailyRecord, RecordExpense.record_id == DailyRecord.id
        ).where(*filters).order_by(
            desc(DailyRecord.record_date), desc(RecordExpense.created_at)
        ).offset(offset).limit(page_size)

        rows = (await session.execute(stmt)).all()

        records = [
            HistoryExpenseItemResponse(
                id=r.id,
                daily_record_id=r.daily_record_id,
                record_date=r.record_date,
                amount=float(r.amount),
                currency=r.currency,
                category=r.category,
                description=r.description,
                source=r.source,
                is_user_confirmed=r.is_user_confirmed,
                created_at=r.created_at,
            )
            for r in rows
        ]

        return HistoryExpenseListResponse(
            total_count=total_count, total_pages=total_pages,
            current_page=page, page_size=page_size, records=records
        )
