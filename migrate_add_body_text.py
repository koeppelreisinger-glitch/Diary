"""
migrate_add_body_text.py
========================
向 daily_records 表追加 body_text TEXT 字段。
项目不使用 Alembic，使用本脚本手动执行 DDL。

运行方式（在项目根目录）：
    python migrate_add_body_text.py

特性：
- 幂等：若列已存在则跳过，不报错
- 同时将已有记录的 body_text 回填为对应 summary_text 的值
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
        # 1. 检查列是否已存在
        check_sql = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'daily_records'
              AND column_name = 'body_text'
              AND table_schema = 'public'
        """)
        result = await conn.execute(check_sql)
        existing = result.fetchone()

        if existing:
            print("[SKIP] body_text 列已存在，无需迁移。")
        else:
            # 2. 添加列（允许 NULL，以便向前兼容旧数据）
            await conn.execute(text("""
                ALTER TABLE daily_records
                ADD COLUMN body_text TEXT NULL
            """))
            print("[OK] body_text 列添加成功。")

            # 3. 回填：把现有所有行的 body_text 设为 summary_text
            result = await conn.execute(text("""
                UPDATE daily_records
                SET body_text = summary_text
                WHERE body_text IS NULL
                  AND deleted_at IS NULL
            """))
            print(f"[OK] 已回填 {result.rowcount} 条记录的 body_text。")

    await engine.dispose()
    print("\n[DONE] 迁移完成。")


if __name__ == "__main__":
    asyncio.run(run_migration())
