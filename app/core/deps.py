import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.exceptions import CredentialsException, ForbiddenException
from app.models.user import User

# 为 FastAPI 指定注入的异步数据库依赖
SessionDep = Annotated[AsyncSession, Depends(get_db)]

# 通过标准 OAuth2 组件自动从 Authorization Header 中提取 Bearer Token
# login 端点仅作 Swagger OpenAPI 展示文档时辅助用（通过引入的 swagger_login 并行处理 Form 数据）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/swagger_login")

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: SessionDep
) -> User:
    """
    基于真实 JWT 的解析及数据库实时校验防线
    拦截任何不合法、已过期、遭软删除与被封禁的人员操作
    """
    # 1. 解析 Access Token
    payload = decode_access_token(token)
    if not payload:
        raise CredentialsException(detail="Token 格式错误、被篡改或已过期")
    
    # 2. 提取并检验 Payload
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise CredentialsException(detail="非法的 Token 负载内容")
        
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise CredentialsException(detail="非法的用户身份标识")

    # 3. 动态验证数据库实体
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    # 4. 判断存续性与业务状态
    if not user:
        raise CredentialsException(detail="无法识别该凭证或账号已被销毁")

    if user.status != "active":
        raise ForbiddenException(detail="您的账号已被禁用，无法执行此操作")

    # 返回完整的 User ORM 实体交由下层 Router 继续派发
    return user

# 将当前登录用户封装为全局一致的显式声明注入依赖
CurrentUser = Annotated[User, Depends(get_current_user)]
