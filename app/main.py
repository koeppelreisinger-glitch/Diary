from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
import logging
import os
import mimetypes

# 必须在所有 ORM 操作前导入全部 Model，否则 relationship 里的字符串引用会解析失败
import app.models  # noqa: F401

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

    # 挂载前端静态文件（本地开发使用；Vercel 由 @vercel/static build 接管）
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    if os.path.isdir(frontend_dir) and not os.environ.get("VERCEL"):
        app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")

    # 挂载用户上传图片目录。
    # Vercel 只能写 /tmp，不能保证长期持久化，但挂载后同实例内的演示图片可正常访问。
    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    if os.environ.get("VERCEL"):
        @app.get("/uploads/{storage_key:path}", include_in_schema=False)
        async def legacy_uploads_blob_proxy(storage_key: str):
            token = os.environ.get("BLOB_READ_WRITE_TOKEN")
            if not token:
                logger.error("[uploads] BLOB_READ_WRITE_TOKEN is not configured")
                return Response(status_code=404)

            tmp_root = os.path.abspath("/tmp/uploads")
            tmp_file_path = os.path.abspath(
                os.path.join(tmp_root, *storage_key.strip("/").split("/"))
            )
            if not (tmp_file_path == tmp_root or tmp_file_path.startswith(tmp_root + os.sep)):
                logger.warning("[uploads] Rejected invalid storage key: %s", storage_key)
                return Response(status_code=404)
            if os.path.isfile(tmp_file_path):
                content_type = mimetypes.guess_type(tmp_file_path)[0] or "application/octet-stream"
                return FileResponse(tmp_file_path, media_type=content_type)

            try:
                from vercel.blob import AsyncBlobClient

                async with AsyncBlobClient(token=token) as client:
                    result = await client.get(storage_key, access="public")
                if result is None or result.status_code != 200 or result.stream is None:
                    logger.warning("[uploads] Blob not found: %s", storage_key)
                    return Response(status_code=404)
                content_type = result.blob.content_type or "application/octet-stream"
                headers = {}
                cache_control = getattr(result.blob, "cache_control", None)
                etag = getattr(result.blob, "etag", None)
                if cache_control:
                    headers["Cache-Control"] = cache_control
                if etag:
                    headers["ETag"] = etag
                return StreamingResponse(result.stream, media_type=content_type, headers=headers)
            except Exception as exc:
                logger.exception("[uploads] Failed to proxy Blob %s: %s", storage_key, exc)
                return Response(status_code=404)
    else:
        os.makedirs(uploads_dir, exist_ok=True)
        app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

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
