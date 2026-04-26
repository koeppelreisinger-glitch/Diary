import uuid
from datetime import datetime, date
from typing import List, Optional

from app.schemas.common import BaseSchema


# ──────────────────────────────────────────────
# 历史记录列表
# ──────────────────────────────────────────────

class HistoryRecordItemResponse(BaseSchema):
    id: uuid.UUID
    record_date: date
    summary_text: str
    emotion_overall_score: int
    keywords: List[str]
    created_at: datetime
    updated_at: datetime


class HistoryListResponse(BaseSchema):
    total_count: int
    total_pages: int
    current_page: int
    page_size: int
    records: List[HistoryRecordItemResponse]


# ──────────────────────────────────────────────
# 日历视图
# ──────────────────────────────────────────────

class HistoryCalendarDayItemResponse(BaseSchema):
    record_date: date
    has_record: bool
    emotion_overall_score: int
    keywords: List[str]
    summary_preview: str


class HistoryCalendarResponse(BaseSchema):
    year: int
    month: int
    days: List[HistoryCalendarDayItemResponse]


# ──────────────────────────────────────────────
# 时间轴视图
# ──────────────────────────────────────────────

class HistoryTimelineItemResponse(BaseSchema):
    id: uuid.UUID
    record_date: date
    summary_preview: str
    emotion_overall_score: int
    keywords: List[str]


class HistoryTimelineGroupResponse(BaseSchema):
    year_month: str
    items: List[HistoryTimelineItemResponse]


class HistoryTimelineResponse(BaseSchema):
    groups: List[HistoryTimelineGroupResponse]


# ──────────────────────────────────────────────
# 五表主视图 — events
# ──────────────────────────────────────────────

class HistoryEventItemResponse(BaseSchema):
    id: uuid.UUID
    daily_record_id: uuid.UUID
    record_date: date
    content: str
    source: str
    is_user_confirmed: bool
    created_at: datetime


class HistoryEventListResponse(BaseSchema):
    total_count: int
    total_pages: int
    current_page: int
    page_size: int
    records: List[HistoryEventItemResponse]


# ──────────────────────────────────────────────
# 五表主视图 — inspirations
# ──────────────────────────────────────────────

class HistoryInspirationItemResponse(BaseSchema):
    id: uuid.UUID
    daily_record_id: uuid.UUID
    record_date: date
    content: str
    source: str
    created_at: datetime


class HistoryInspirationListResponse(BaseSchema):
    total_count: int
    total_pages: int
    current_page: int
    page_size: int
    records: List[HistoryInspirationItemResponse]


# ──────────────────────────────────────────────
# 五表主视图 — emotions
# ──────────────────────────────────────────────

class HistoryEmotionItemResponse(BaseSchema):
    id: uuid.UUID
    daily_record_id: uuid.UUID
    record_date: date
    emotion_label: str
    intensity: int
    source: str
    is_user_confirmed: bool
    created_at: datetime


class HistoryEmotionListResponse(BaseSchema):
    total_count: int
    total_pages: int
    current_page: int
    page_size: int
    records: List[HistoryEmotionItemResponse]


# ──────────────────────────────────────────────
# 五表主视图 — locations
# ──────────────────────────────────────────────

class HistoryLocationItemResponse(BaseSchema):
    id: uuid.UUID
    daily_record_id: uuid.UUID
    record_date: date
    name: str
    source: str
    is_user_confirmed: bool
    created_at: datetime


class HistoryLocationListResponse(BaseSchema):
    total_count: int
    total_pages: int
    current_page: int
    page_size: int
    records: List[HistoryLocationItemResponse]


# ──────────────────────────────────────────────
# 五表主视图 — expenses
# ──────────────────────────────────────────────

class HistoryExpenseItemResponse(BaseSchema):
    id: uuid.UUID
    daily_record_id: uuid.UUID
    record_date: date
    amount: float
    currency: str
    category: Optional[str]
    description: Optional[str]
    source: str
    is_user_confirmed: bool
    created_at: datetime


class HistoryExpenseListResponse(BaseSchema):
    total_count: int
    total_pages: int
    current_page: int
    page_size: int
    records: List[HistoryExpenseItemResponse]
