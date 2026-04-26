import uuid
from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserSetting(Base):
    """
    用户设置模型
    """
    __tablename__ = "user_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # 持有外键，并加上 unique 约束保证 1:1
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        unique=True, 
        index=True, 
        nullable=False,
        comment="关联用户，1:1关系强制唯一"
    )
    
    timezone: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        default="UTC", 
        comment="用户时区 (IANA 标识，如 Asia/Shanghai)"
    )
    
    input_preference: Mapped[str] = mapped_column(
        String(20), 
        nullable=False, 
        default="mixed", 
        comment="输入偏好：text / voice / mixed"
    )
    
    reminder_enabled: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        default=False, 
        comment="是否开启每日日记提醒"
    )
    
    reminder_time: Mapped[time | None] = mapped_column(
        Time(timezone=False),
        nullable=True,
        comment="每日提醒时间 (HH:MM)"
    )

    is_dark_mode: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="是否启用深色模式"
    )

    # 关联关系
    user: Mapped["User"] = relationship(
        "User", 
        back_populates="user_setting"
    )
