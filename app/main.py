from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
import logging
import os

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.api.router import api_router
from app.core.exceptions import ErrorResponseAPIException

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json"
    )

    # 跨域设置
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # 注册 API 路由
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # 挂载前端静态文件
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    if os.path.isdir(frontend_dir):
        app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")

    # 注册全局异常处理：覆盖默认的 422 格式
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "code": 40001,
                "message": "参数校验失败",
                "data": exc.errors()
            }
        )

    # 注册全局自定义业务异常处理
    @app.exception_handler(ErrorResponseAPIException)
    async def custom_api_exception_handler(request: Request, exc: ErrorResponseAPIException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": str(exc.detail),
                "data": None
            }
        )

    # ── 启动事件：打印配置摘要，快速定位部署问题 ──
    @app.on_event("startup")
    async def _startup_config_check():
        db_url = settings.SQLALCHEMY_DATABASE_URI
        is_localhost = "localhost" in db_url or "127.0.0.1" in db_url
        has_ai_auth = bool(
            (settings.TOKENHUB_AUTHORIZATION or "").strip()
            or (settings.TOKENHUB_API_KEY or "").strip()
        )

        logger.info("=" * 60)
        logger.info("Echo Backend 启动配置检查")
        logger.info("  DB: %s", "localhost（⚠️ 服务器部署时会 500）" if is_localhost else "云数据库 ✓")
        logger.info("  AI Auth: %s", "已配置 ✓" if has_ai_auth else "未配置（AI 功能不可用）")
        logger.info("  Secret Key 默认值: %s", settings.SECRET_KEY == "REPLACE_THIS_WITH_A_SECURE_SECRET_KEY")
        logger.info("=" * 60)

        if is_localhost and os.environ.get("VERCEL"):
            logger.error(
                "[致命] Vercel 环境检测到数据库指向 localhost！"
                "请在 Vercel Dashboard > Settings > Environment Variables 中设置 DATABASE_URL。"
            )

    # ── 临时诊断端点：返回数据库连接的真实错误信息 ──────────────────
    @app.get("/debug/db-test")
    async def _debug_db_test():
        """临时端点，排查数据库连接问题后删除"""
        import traceback, os
        from sqlalchemy import text
        from app.core.database import engine, _raw_db_url, _needs_ssl, _is_pooler
        raw_env = os.environ.get("DATABASE_URL", "NOT_SET")
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                row = result.scalar()
            return {
                "status": "ok",
                "db_ping": row,
                "db_host": _raw_db_url.split("@")[-1].split("/")[0] if "@" in _raw_db_url else "?",
                "ssl": _needs_ssl,
                "pooler": _is_pooler,
                "env_db_url_set": raw_env != "NOT_SET",
                "env_db_url_preview": raw_env[:50] if raw_env != "NOT_SET" else "NOT_SET",
            }
        except Exception as e:
            return JSONResponse(status_code=200, content={
                "status": "error",
                "error_type": type(e).__name__,
                "error_msg": str(e)[:500],
                "traceback": traceback.format_exc()[-800:],
                "ssl": _needs_ssl,
                "pooler": _is_pooler,
                "raw_url_host": _raw_db_url.split("@")[-1].split("/")[0] if "@" in _raw_db_url else "?",
                "env_db_url_set": raw_env != "NOT_SET",
                "env_db_url_preview": raw_env[:50] if raw_env != "NOT_SET" else "NOT_SET",
            })


    return app

app = create_app()

@app.get("/", include_in_schema=False)
async def root_redirect():
    """根路径重定向到前端登录页"""
    return RedirectResponse(url="/frontend/login.html")

@app.get("/health", tags=["system"])
async def health_check():
    """
    检查系统健康状态
    """
    return {
        "code": 20000,
        "message": "success",
        "data": {
            "status": "ok", 
            "version": settings.VERSION
        }
    }
