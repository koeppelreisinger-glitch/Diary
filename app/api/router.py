from fastapi import APIRouter

from app.api.routes import auth, settings, conversations, daily_records, history, media

api_router = APIRouter()

# 注册构建好的认证与全局设置模块路由
api_router.include_router(auth.router)
api_router.include_router(settings.router)
api_router.include_router(conversations.router)
api_router.include_router(daily_records.router)
api_router.include_router(history.router)
api_router.include_router(media.router)


@api_router.get("/", tags=["system"])
async def root_status():
    return {
        "code": 20000,
        "message": "success",
        "data": {
            "message": "Echo API is online."
        }
    }
