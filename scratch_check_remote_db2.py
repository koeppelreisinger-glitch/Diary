import asyncio
import ssl
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://neondb_owner:npg_teNAu6Ga8hfo@ep-snowy-wind-amx8rt0e.c-5.us-east-1.aws.neon.tech/neondb"

async def check():
    ssl_context = ssl.create_default_context()
    engine = create_async_engine(DATABASE_URL, connect_args={"ssl": ssl_context})
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='daily_record_images'"))
        columns = [row[0] for row in result.fetchall()]
        print("Columns in daily_record_images:")
        print(columns)
        
asyncio.run(check())
