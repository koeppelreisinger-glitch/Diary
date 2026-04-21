import os
import ssl
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Serverless 环境（Vercel）下不能用连接池，否则每次冷启动都会泳漏连接导致 500
is_serverless = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))

# asyncpg 不支持 URL 里的 ssl=require，需通过 connect_args 传入 SSLContext
# 检测原始 DATABASE_URL 是否要求 SSL
_raw_db_url = settings.DATABASE_URL or ""
_needs_ssl = any(x in _raw_db_url for x in ("sslmode=require", "ssl=require", "neon.tech", "supabase.co"))
_connect_args = {"ssl": ssl.create_default_context()} if _needs_ssl else {}

if is_serverless:
    engine = create_async_engine(
        settings.SQLALCHEMY_DATABASE_URI,
        echo=False,
        poolclass=NullPool,  # Serverless: 无连接池
        connect_args=_connect_args,
    )
else:
    engine = create_async_engine(
        settings.SQLALCHEMY_DATABASE_URI,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        connect_args=_connect_args,
    )

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    提供给依赖注入通过 yield 返回数据库会话。
    本依赖只负责提供 session 和在抛出异常时回滚连接；
    事务的提交 (commit) 必须交给业务 service 层显式控制，避免引发复杂的事务边界混乱。
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
