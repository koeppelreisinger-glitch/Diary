import asyncio
import os
import ssl
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://neondb_owner:npg_teNAu6Ga8hfo@ep-snowy-wind-amx8rt0e.c-5.us-east-1.aws.neon.tech/neondb"

async def check_schema():
    ssl_context = ssl.create_default_context()
    engine = create_async_engine(DATABASE_URL, connect_args={"ssl": ssl_context})
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='daily_record_images'"))
        columns = [row[0] for row in result.fetchall()]
        print("Columns in daily_record_images:")
        print(columns)
        if "deleted_at" not in columns:
            print("Fixing schema by adding deleted_at...")
            await conn.execute(text("ALTER TABLE daily_record_images ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;"))
            await conn.commit()
            print("Fixed!")
        else:
            print("Column already exists.")
            
asyncio.run(check_schema())
