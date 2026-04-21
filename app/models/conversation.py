import uuid
from datetime import date
from sqlalchemy import String, Date, ForeignKey, Index, Text, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class Conversation(Base):
    """每日会话主表"""
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        index=True, 
        nullable=False,
        comment="关联用户"
    )
    record_date: Mapped[date] = mapped_column(
        Date, 
        nullable=False, 
        comment="会话归属的用户本地自然日"
    )
    status: Mapped[str] = mapped_column(
        String(20), 
        nullable=False, 
        default="recording", 
        comment="会话状态：recording / completing / completed"
    )
    extra_json: Mapped[dict | None] = mapped_column(
        JSONB, 
        nullable=True, 
        comment="可选扩展字段"
    )

    # 放弃在 __table_args__ 内定部分索引的 Hack 写法，全部由下方的全局 Index 接管
    # 这里不需要 __table_args__


    messages = relationship(
        "ConversationMessage", 
        back_populates="conversation", 
        cascade="all, delete-orphan",
        order_by="ConversationMessage.sequence_number"
    )

# 动态绑定带有条件的部分唯一索引
Index(
    "uq_conversations_user_id_record_date",
    Conversation.user_id,
    Conversation.record_date,
    unique=True,
    postgresql_where=Conversation.deleted_at.is_(None)
)


class ConversationMessage(Base):
    """会话内消息流水记录表"""
    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("conversations.id", ondelete="CASCADE"), 
        index=True, 
        nullable=False,
        comment="关联会话"
    )
    role: Mapped[str] = mapped_column(
        String(20), 
        nullable=False, 
        comment="发送方角色：user / ai"
    )
    content_type: Mapped[str] = mapped_column(
        String(20), 
        nullable=False, 
        comment="内容类型：text / voice"
    )
    content: Mapped[str] = mapped_column(
        Text, 
        nullable=False, 
        comment="消息文本内容"
    )
    media_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), 
        nullable=True, 
        comment="关联媒体文件（可选）"
    )
    sequence_number: Mapped[int] = mapped_column(
        Integer, 
        nullable=False, 
        comment="消息在当前会话内的有序序号"
    )

    __table_args__ = (
        UniqueConstraint(
            "conversation_id", 
            "sequence_number", 
            name="uq_conversation_messages_conversation_id_sequence_number"
        ),
    )

    conversation = relationship("Conversation", back_populates="messages")
