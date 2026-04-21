"""
init_db.py — 一次性建表脚本
使用 SQLAlchemy async engine + Base.metadata.create_all() 在 echo_db 中创建所有表。
不使用 Alembic，不做迁移管理。
"""

import asyncio
import sys

# Windows 上 asyncpg 需要 SelectorEventLoop，ProactorEventLoop（默认）会导致连接中断
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.models.base import Base

# ── 必须显式导入所有模型，让它们注册到 Base.metadata ──
from app.models.user import User           # noqa: F401
from app.models.user_setting import UserSetting  # noqa: F401
from app.models.conversation import Conversation, ConversationMessage  # noqa: F401
from app.models.daily_record import (
    DailyRecord, RecordEvent, RecordEmotion, RecordExpense, RecordLocation, RecordTag
)  # noqa: F401



async def init_db() -> None:
    engine = create_async_engine(
        settings.SQLALCHEMY_DATABASE_URI,
        echo=True,          # 打印 DDL SQL，方便确认
        pool_pre_ping=True,
    )

    async with engine.begin() as conn:
        # run_sync 让同步的 create_all 在异步上下文内运行
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    print("\n[OK] 表创建成功：users, user_settings, conversations, conversation_messages")


if __name__ == "__main__":
    asyncio.run(init_db())
