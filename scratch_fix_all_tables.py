import asyncio
import ssl
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://neondb_owner:npg_teNAu6Ga8hfo@ep-snowy-wind-amx8rt0e.c-5.us-east-1.aws.neon.tech/neondb"

TABLES = [
    "users",
    "user_settings",
    "conversations",
    "conversation_messages",
    "daily_records",
    "record_events",
    "record_emotions",
    "record_expenses",
    "record_locations",
    "record_tags",
    "daily_record_images"
]

async def fix_schema():
    ssl_context = ssl.create_default_context()
    engine = create_async_engine(DATABASE_URL, connect_args={"ssl": ssl_context})
    async with engine.connect() as conn:
        for table in TABLES:
            result = await conn.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}'"))
            columns = [row[0] for row in result.fetchall()]
            if "deleted_at" not in columns and len(columns) > 0:
                print(f"Adding deleted_at to {table}...")
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;"))
            elif len(columns) == 0:
                print(f"Table {table} does not exist!")
            else:
                print(f"Table {table} already has deleted_at.")
        
        await conn.commit()
    await engine.dispose()
    print("All tables checked and fixed.")

asyncio.run(fix_schema())
