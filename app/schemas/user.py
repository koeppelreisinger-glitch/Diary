import uuid
from datetime import datetime
from typing import Optional
from pydantic import Field
from app.schemas.common import BaseSchema

class CurrentUserResponse(BaseSchema):
    """
    当前登录用户的返回结构
    包含从 User ORM 转换出的暴露字段
    """
    id: uuid.UUID = Field(description="用户唯一标识")
    phone: str = Field(description="脱敏后的手机号")
    email: Optional[str] = Field(None, description="邮箱，暂不强制")
    nickname: str = Field(description="用户昵称")
    avatar_url: Optional[str] = Field(None, description="头像地址")
    status: str = Field(description="状态：active / banned")
    last_login_at: Optional[datetime] = Field(None, description="最后登录时间")
    created_at: datetime = Field(description="注册时间")


class UpdateUserRequest(BaseSchema):
    """
    用户自主更新信息的请求体，仅允许暴露限定字段
    """
    nickname: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="新的昵称，允许 1 到 50 字符"
    )
    avatar_url: Optional[str] = Field(
        None,
        max_length=255,
        description="新的头像绝对路径地址"
    )


class UserStatsResponse(BaseSchema):
    """
    用户统计数据：供「我的」与「希冀」页面展示
    """
    total_days: int = Field(description="累计记录日记天数")
    current_streak: int = Field(description="当前连续打卡天数（从今天或昨天向前推）")
    total_events: int = Field(description="累计记录事件总条数")
