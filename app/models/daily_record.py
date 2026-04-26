import uuid
from datetime import date
from sqlalchemy import String, Date, ForeignKey, Index, Text, Integer, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class DailyRecord(Base):
    """每日总结主记录"""
    __tablename__ = "daily_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    record_date: Mapped[date] = mapped_column(
        Date,
        index=True,
        nullable=False,
    )
    # ── 正文主字段：用户可编辑的全量日记文本 ──────────────────
    # body_text 是结构化重建的"源文本"；首次生成时与 summary_text 相同。
    # 用户手动改写或 AI 追加后，以 body_text 为准触发全量重建。
    body_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="日记正文主字段（可编辑源文本）；旧记录可能为 NULL",
    )
    # ── 摘要：供列表/头部展示的短文本 ────────────────────────
    summary_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    emotion_overall_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    keywords: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list
    )
    user_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    extra_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    events = relationship("RecordEvent", back_populates="record", cascade="all, delete-orphan")
    emotions = relationship("RecordEmotion", back_populates="record", cascade="all, delete-orphan")
    expenses = relationship("RecordExpense", back_populates="record", cascade="all, delete-orphan")
    locations = relationship("RecordLocation", back_populates="record", cascade="all, delete-orphan")
    inspirations = relationship("RecordInspiration", back_populates="record", cascade="all, delete-orphan")
    images = relationship("DailyRecordImage", back_populates="record", cascade="all, delete-orphan")

Index(
    "uq_daily_records_user_id_record_date",
    DailyRecord.user_id,
    DailyRecord.record_date,
    unique=True,
    postgresql_where=DailyRecord.deleted_at.is_(None)
)


class RecordEvent(Base):
    """当日提取的事件条目"""
    __tablename__ = "record_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daily_records.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    is_user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    record = relationship("DailyRecord", back_populates="events")


class RecordEmotion(Base):
    """当日提取的情绪标注条目"""
    __tablename__ = "record_emotions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daily_records.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    emotion_label: Mapped[str] = mapped_column(String(50), nullable=False)
    intensity: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    is_user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extra_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    record = relationship("DailyRecord", back_populates="emotions")


class RecordExpense(Base):
    """当日提取的消费记录条目"""
    __tablename__ = "record_expenses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daily_records.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    is_user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    record = relationship("DailyRecord", back_populates="expenses")


class RecordLocation(Base):
    """当日提取的地点信息条目"""
    __tablename__ = "record_locations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daily_records.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    is_user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    record = relationship("DailyRecord", back_populates="locations")


class RecordInspiration(Base):
    """当日灵感记录条目"""
    __tablename__ = "record_inspirations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daily_records.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)

    record = relationship("DailyRecord", back_populates="inspirations")
