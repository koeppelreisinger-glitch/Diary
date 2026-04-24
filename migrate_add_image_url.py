"""
migrate_add_image_url.py
========================
向 conversation_messages 表追加 image_url TEXT 字段。
项目不使用 Alembic，使用本脚本手动执行 DDL。

根因：image_url 是后加入 ORM 模型的字段，但 init_db.py 的 create_all
     只建新表、不更新已有表列，导致 SQLAlchemy SELECT 时命中 PostgreSQL
     UndefinedColumn 错误，造成 /conversations/{id}/messages 返回 500。

运行方式（在项目根目录）：
    python migrate_add_image_url.py

特性：
- 幂等：若列已存在则跳过，不报错
- 已有消息行的 image_url 默认值为 NULL（允许 NULL，向前兼容）
"""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from app.core.config import settings


async def run_migration() -> None:
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, echo=True)

    async with engine.begin() as conn:
        # 1. 检查 image_url 列是否已存在
        check_sql = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name   = 'conversation_messages'
              AND column_name  = 'image_url'
              AND table_schema = 'public'
        """)
        result = await conn.execute(check_sql)
        existing = result.fetchone()

        if existing:
            print("[SKIP] conversation_messages.image_url 列已存在，无需迁移。")
        else:
            await conn.execute(text("""
                ALTER TABLE conversation_messages
                ADD COLUMN image_url TEXT NULL
            """))
            print("[OK] conversation_messages.image_url 列添加成功。")

    await engine.dispose()
    print("\n[DONE] 迁移完成。")


if __name__ == "__main__":
    asyncio.run(run_migration())
