import asyncio
import os
import sys
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# 将项目根目录加入 path 以导入 settings
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings

async def diagnose():
    db_url = settings.SQLALCHEMY_DATABASE_URI
    print(f"正在诊断数据库: {db_url.split('@')[-1]}")
    
    engine = create_async_engine(db_url)
    
    async with engine.connect() as conn:
        # 1. 检查各表结构
        for table in ["users", "user_settings"]:
            print(f"\n--- {table} 结构 ---")
            res = await conn.execute(text(
                f"SELECT column_name, data_type, is_nullable, column_default "
                f"FROM information_schema.columns WHERE table_name='{table}'"
            ))
            for row in res.fetchall():
                print(row)

        # 2. 尝试模拟一次 UserSetting 插入（不提交）
        print("\n--- 尝试模拟插入 UserSetting ---")
        try:
            # 这里的 user_id 是虚构的，我们只看字段错误
            test_id = uuid.uuid4()
            await conn.execute(text(
                "INSERT INTO user_settings (id, user_id, timezone, input_preference, is_dark_mode) "
                "VALUES (:id, :uid, 'UTC', 'mixed', false)"
            ), {"id": uuid.uuid4(), "uid": test_id})
            print("插入尝试成功（如果是真实的 UID）")
        except Exception as e:
            print(f"插入尝试失败: {e}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(diagnose())
