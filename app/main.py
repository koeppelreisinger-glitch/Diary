from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
import os

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
