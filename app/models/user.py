import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    # 避免循环引用
    from app.models.user_setting import UserSetting


class User(Base):
    """
    用户模型
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    phone: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False, comment="手机号，MVP 核心登录主凭据"
    )
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True, comment="用户邮箱，后续扩展使用"
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="哈希后的密码"
    )
    nickname: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="用户昵称"
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="用户头像地址"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最后登录时间"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", comment="状态：active / banned"
    )

    # 1:1 双向关联关系
    # user_settings 表是持有外键的一方。这侧设置 uselist=False 来保证 1:1
    user_setting: Mapped["UserSetting"] = relationship(
        "UserSetting", 
        back_populates="user", 
        cascade="all, delete-orphan", 
        uselist=False
    )
