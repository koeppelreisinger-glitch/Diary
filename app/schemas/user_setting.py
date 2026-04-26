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
    is_dark_mode: bool = Field(default=False, description="是否启用深色模式")
    updated_at: datetime = Field(description="最近一次更新时间")

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
    is_dark_mode: Optional[bool] = Field(
        None,
        description="是否开启深色模式"
    )
