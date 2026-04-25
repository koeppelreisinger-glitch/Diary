import asyncio
import sys
import ssl

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy.ext.asyncio import create_async_engine
from app.models.base import Base

from app.models.user import User
from app.models.user_setting import UserSetting
from app.models.conversation import Conversation, ConversationMessage
from app.models.daily_record import DailyRecord, RecordEvent, RecordEmotion, RecordExpense, RecordLocation, RecordTag
from app.models.media import DailyRecordImage

DATABASE_URL = "postgresql+asyncpg://neondb_owner:npg_teNAu6Ga8hfo@ep-snowy-wind-amx8rt0e.c-5.us-east-1.aws.neon.tech/neondb"

async def init_db() -> None:
    ssl_context = ssl.create_default_context()
    engine = create_async_engine(
        DATABASE_URL,
        echo=True,
        pool_pre_ping=True,
        connect_args={"ssl": ssl_context}
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    print("Remote DB schema initialized successfully!")

if __name__ == "__main__":
    asyncio.run(init_db())
