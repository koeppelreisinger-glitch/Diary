from typing import List, Optional
import uuid
from datetime import datetime, date
from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema


class ConversationMessageResponse(BaseSchema):
    id: uuid.UUID = Field(description="消息 ID")
    role: str = Field(description="发送方角色：user / ai")
    content_type: str = Field(description="内容类型：text / voice")
    content: str = Field(description="消息文本内容")
    media_file_id: Optional[uuid.UUID] = Field(None, description="语音类型消息的媒体文件 ID")
    image_url: Optional[str] = Field(None, description="消息附带的图片 URL")
    sequence_number: int = Field(description="消息在会话内的有序序号")
    created_at: datetime = Field(description="消息写入时间")


class ConversationResponse(BaseSchema):
    id: uuid.UUID = Field(description="会话 ID")
    status: str = Field(description="会话状态：recording / completing / completed")
    record_date: date = Field(description="会话归属的用户本地日期")
    message_count: int = Field(default=0, description="当前会话的消息总数")
    created_at: datetime = Field(description="会话创建时间")
    updated_at: datetime = Field(description="会话最近更新时间")


class TodayConversationResponse(BaseSchema):
    has_today: bool = Field(description="今日是否已存在会话记录")
    conversation: Optional[ConversationResponse] = Field(None, description="今日会话对象")


class CreateConversationResponse(BaseSchema):
    id: uuid.UUID
    status: str
    record_date: date
    created_at: datetime


class MessageListResponse(BaseSchema):
    conversation_id: uuid.UUID
    total_count: int
    messages: List[ConversationMessageResponse]


class SendMessageRequest(BaseSchema):
    content_type: str = Field(..., description="消息内容类型：text / voice")
    content: Optional[str] = Field(None, description="消息文本内容，text类型必填")
    media_file_id: Optional[uuid.UUID] = Field(None, description="媒体文件ID，voice类型必填")
    image_url: Optional[str] = Field(None, description="已上传图片的访问 URL（可选）")
    # ── Phase 2 新增 ────────────────────────────────────────────
    # 置为 True 时，允许在 completed 会话中继续发送"补充消息"并触发 AI 回复。
    # 默认 False，保持原有行为不变。
    is_supplement: bool = Field(
        default=False,
        description="是否为补写阶段的补充消息；True 时 completed 会话可继续收到消息"
    )


class SendMessageResponse(BaseSchema):
    user_message: ConversationMessageResponse
    ai_message: ConversationMessageResponse


from app.schemas.daily_record import DailyRecordDetailResponse  # noqa: E402


class CompleteConversationResponse(BaseSchema):
    conversation_id: uuid.UUID
    status: str
    updated_at: datetime
    daily_record: DailyRecordDetailResponse
