"""直接测试注册逻辑，捕获完整 traceback"""
import asyncio
import sys
import traceback

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.database import AsyncSessionLocal
from app.schemas.auth import RegisterRequest
from app.services.auth_service import AuthService


async def main():
    async with AsyncSessionLocal() as session:
        try:
            req = RegisterRequest(
                phone="13800138000",
                password="Test1234!",
                nickname="test"
            )
            result = await AuthService.register_user(session, req)
            print("SUCCESS:", result.model_dump())
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
