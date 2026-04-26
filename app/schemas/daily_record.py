import uuid
from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel, Field, field_validator

from app.schemas.common import BaseSchema


class RecordEventResponse(BaseSchema):
    id: uuid.UUID
    content: str
    source: str
    is_user_confirmed: bool
    created_at: datetime


class RecordEmotionResponse(BaseSchema):
    id: uuid.UUID
    emotion_label: str
    intensity: int
    source: str
    is_user_confirmed: bool
    created_at: datetime


class RecordExpenseResponse(BaseSchema):
    id: uuid.UUID
    amount: float
    currency: str
    category: Optional[str]
    description: Optional[str]
    source: str
    is_user_confirmed: bool
    created_at: datetime


class RecordLocationResponse(BaseSchema):
    id: uuid.UUID
    name: str
    source: str
    is_user_confirmed: bool
    created_at: datetime


class RecordInspirationResponse(BaseSchema):
    id: uuid.UUID
    content: str
    source: str
    created_at: datetime


class DailyRecordDetailResponse(BaseSchema):
    id: uuid.UUID
    conversation_id: uuid.UUID          # 关联会话 ID，前端补充对话时使用
    record_date: date
    body_text: Optional[str] = None
    summary_text: str
    emotion_overall_score: int
    keywords: List[str]
    user_note: Optional[str]
    events: List[RecordEventResponse]
    emotions: List[RecordEmotionResponse]
    expenses: List[RecordExpenseResponse]
    locations: List[RecordLocationResponse]
    inspirations: List[RecordInspirationResponse]
    created_at: datetime
    updated_at: datetime


class TodayDailyRecordResponse(BaseSchema):
    has_record: bool
    is_generating: bool
    record: Optional[DailyRecordDetailResponse] = None


# ── 轻量标注编辑请求 ──────────────────────────────────────
class UpdateDailyRecordRequest(BaseSchema):
    user_note: Optional[str] = Field(None, description="用户备注；显式传入 null 可清空；未传则保持不变")
    keywords: Optional[List[str]] = Field(None, description="关键词字符串数组；整体覆盖现有值")
    inspirations_to_add: Optional[List[str]] = Field(None, description="新增的灵感内容列表；新增前会 strip()，空字符串会被忽略")
    inspirations_to_remove: Optional[List[uuid.UUID]] = Field(None, description="需移除的灵感记录 ID 列表")


# ── Phase 1：手动改正文请求模型 ───────────────────────────
class UpdateDailyRecordBodyRequest(BaseSchema):
    body_text: str = Field(..., description="用户修改后的完整日记正文；不得为空白字符串")

    @field_validator("body_text")
    @classmethod
    def body_text_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("body_text 不能为空白字符串")
        return v


# ── Phase 2：保存本次补充请求模型 ─────────────────────────
class SaveSupplementRequest(BaseSchema):
    """
    "保存本次补充"接口的请求体。
    前端不需要自行传递正文内容，后端会从 conversation 的完整消息历史中
    重新推导出最新的 body_text，再触发全量重建。
    预留 note 字段供将来扩展，当前版本忽略该字段。
    """
    note: Optional[str] = Field(
        default=None,
        description="（可选）本次补充的附加备注；当前版本后端不处理此字段，留作扩展"
    )


# ── 补录日记：从正文直接创建（适合过往无记录日期手动补录） ──
class CreateManualRecordRequest(BaseSchema):
    record_date: date = Field(..., description="要补录的日期，格式 YYYY-MM-DD")
    body_text: str = Field(..., description="日记正文内容，不得为空白字符串")

    @field_validator("body_text")
    @classmethod
    def body_text_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("body_text 不能为空白字符串")
        return v
