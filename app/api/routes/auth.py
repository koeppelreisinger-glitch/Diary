from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.core.deps import SessionDep, CurrentUser
from app.schemas.auth import RegisterRequest, LoginRequest, LoginResponse
from app.schemas.user import CurrentUserResponse, UpdateUserRequest, UserStatsResponse
from app.schemas.common import ApiResponse
from app.services.auth_service import AuthService

router = APIRouter()

@router.post("/auth/register", response_model=ApiResponse[CurrentUserResponse], tags=["Auth"])
async def register(
    request: RegisterRequest, 
    session: SessionDep
):
    """用户注册（目前仅限手机号为主凭据，自动初始化配置）"""
    user_resp = await AuthService.register_user(session, request)
    return ApiResponse(
        code=20000,
        message="注册成功",
        data=user_resp
    )


@router.post("/auth/login", response_model=ApiResponse[LoginResponse], tags=["Auth"])
async def login(
    request: LoginRequest, 
    session: SessionDep
):
    """实体的用户登录接口（强制面向前端等客户端使用 strict JSON 传参通信）"""
    login_resp = await AuthService.login_user(session, request)
    return ApiResponse(
        code=20000,
        message="登录成功",
        data=login_resp
    )


@router.post("/auth/swagger_login", include_in_schema=False)
async def swagger_login(
    session: SessionDep,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    被隐藏的专门为 Swagger UI Authorize 右上角按钮提供底层支持的劫持接口。
    因为 Swagger OpenAPI 的 Oauth2 Bearer 强制要求以 x-www-form-urlencoded 标准的 Form 提交，
    并且其 Token 解析不识别项目定义的 ApiResponse 嵌套包结构（须扁平返回），
    故由此路由接管调试界面请求，解决"登录授权按钮一点就报错 / 找不到端口"类文档解析错误现象。
    """
    request = LoginRequest(phone=form_data.username, password=form_data.password)
    login_resp = await AuthService.login_user(session, request)
    return {
        "access_token": login_resp.access_token,
        "token_type": login_resp.token_type
    }


@router.get("/users/me", response_model=ApiResponse[CurrentUserResponse], tags=["Users"])
async def get_current_user_info(
    current_user: CurrentUser
):
    """获取当前登录用户信息（带手机号脱敏机制）"""
    user_resp = AuthService.get_current_user_profile(current_user)
    return ApiResponse(
        code=20000,
        message="success",
        data=user_resp
    )


@router.put("/users/me", response_model=ApiResponse[CurrentUserResponse], tags=["Users"])
async def update_current_user_info(
    request: UpdateUserRequest,
    session: SessionDep,
    current_user: CurrentUser
):
    """局部自更新用户信息（昵称/头像隔离保护）"""
    user_resp = await AuthService.update_user_profile(session, current_user, request)
    return ApiResponse(
        code=20000,
        message="更新成功",
        data=user_resp
    )


@router.get("/users/stats", response_model=ApiResponse[UserStatsResponse], tags=["Users"])
async def get_user_stats(
    session: SessionDep,
    current_user: CurrentUser
):
    """获取用户统计数据：累计记录天数、当前连续打卡天数、累计事件数"""
    stats = await AuthService.get_user_stats(session, current_user)
    return ApiResponse(
        code=20000,
        message="success",
        data=stats
    )
