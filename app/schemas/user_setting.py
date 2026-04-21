import uuid
from datetime import time, datetime
from typing import Literal, Optional
from pydantic import Field, field_validator
from app.schemas.common import BaseSchema

class UserSettingsResponse(BaseSchema):
    """
    用户设置明细返回结构
    """
    user_id: uuid.UUID = Field(description="归属用户 ID")
    timezone: str = Field(description="时区 IANA 标识，如 Asia/Shanghai")
    input_preference: Literal["text", "voice", "mixed"] = Field(
        description="输入偏好：text / voice / mixed"
    )
    reminder_enabled: bool = Field(description="是否开启提醒")
    reminder_time: Optional[str] = Field(
        None, 
        description="每日提醒时间串（HH:MM）"
    )
    updated_at: datetime = Field(description="最近一次更新时间")

    @field_validator("reminder_time", mode="before")
    @classmethod
    def format_time_from_db(cls, v):
        """保证将从 DB 选取的 datetime.time 对象转化为前端需要的 HH:MM"""
        if isinstance(v, time):
            return v.strftime("%H:%M")
        return v

class UpdateUserSettingsRequest(BaseSchema):
    """
    局部更新用户设置的请求体
    所有字段均为 Optional
    """
    timezone: Optional[str] = Field(
        None, 
        max_length=50, 
        description="拟更替的时区 IANA 标识"
    )
    input_preference: Optional[Literal["text", "voice", "mixed"]] = Field(
        None, 
        description="设定新的主反馈输入偏好"
    )
    reminder_enabled: Optional[bool] = Field(
        None, 
        description="动态开关单日提醒"
    )
    reminder_time: Optional[str] = Field(
        None, 
        pattern=r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$", 
        description="合法的 24 小时制表达如 08:30"
    )

    # 备注：在文档规范中提及若 reminder_enabled 为 True 则必有时间，这部分将交由 API Service 中执行强制校验。
