import uuid
from datetime import date

from sqlalchemy import String, Date, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class DailyRecordImage(Base):
    """日记图片表 — 每张图片对应用户某天的记录"""

    __tablename__ = "daily_record_images"

    # ── 主键 ──
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── 外键 ──
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="关联用户",
    )
    daily_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("daily_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联日记（可空，上传时当天尚无日记则为 NULL）",
    )

    # ── 日期（冗余，便于按日期查询）──
    record_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="图片归属日期",
    )

    # ── 存储信息 ──
    storage_key: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="本地或云存储路径 Key"
    )
    url: Mapped[str] = mapped_column(
        String(1024), nullable=False, comment="公开访问 URL"
    )
    thumbnail_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, comment="缩略图 URL（异步生成）"
    )

    # ── 文件元信息 ──
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="image/jpeg / image/png / image/webp"
    )
    file_size: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="文件大小（字节）"
    )
    width: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="像素宽度")
    height: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="像素高度")

    # ── 来源追踪（可选）──
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="发送时所在的对话 ID",
    )

    # ── AI 分析（异步后台填充）──
    ai_caption: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI 图片描述（Vision 生成）"
    )
    ai_tags: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI 标签 JSON 数组，如 '[\"书店\",\"室内\"]'"
    )
    dominant_colors: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="主色调 JSON 数组，如 '[\"#F5D76E\"]'"
    )

    # ── 关联关系 ──
    record = relationship(
        "DailyRecord",
        back_populates="images",
        foreign_keys=[daily_record_id],
    )
