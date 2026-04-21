from fastapi import APIRouter

from app.core.deps import SessionDep, CurrentUser
from app.schemas.user_setting import UserSettingsResponse, UpdateUserSettingsRequest
from app.schemas.common import ApiResponse
from app.services.user_setting_service import UserSettingService

router = APIRouter()

@router.get("/settings", response_model=ApiResponse[UserSettingsResponse], tags=["Settings"])
async def get_user_settings(
    session: SessionDep,
    current_user: CurrentUser
):
    """获取当前登录用户的偏好设定"""
    # 按照最终预期，此处提取通过鉴权校验过后的 User 主键直接对接查询服务
    settings_resp = await UserSettingService.get_user_settings(session, current_user.id)
    return ApiResponse(
        code=20000,
        message="success",
        data=settings_resp
    )

@router.put("/settings", response_model=ApiResponse[UserSettingsResponse], tags=["Settings"])
async def update_user_settings(
    request: UpdateUserSettingsRequest,
    session: SessionDep,
    current_user: CurrentUser
):
    """修改当前登录用户的偏好设定（支持局部修改）"""
    settings_resp = await UserSettingService.update_user_settings(session, current_user.id, request)
    return ApiResponse(
        code=20000,
        message="更新成功",
        data=settings_resp
    )
