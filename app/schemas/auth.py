from typing import Optional
from pydantic import Field
from app.schemas.common import BaseSchema

class RegisterRequest(BaseSchema):
    """
    新用户注册请求体
    """
    phone: str = Field(
        ..., 
        min_length=8, 
        max_length=20, 
        pattern=r"^\+?[0-9\s-]+$", 
        description="手机号，支持数字与国别码符号"
    )
    password: str = Field(
        ..., 
        min_length=8, 
        max_length=128, 
        description="密码原文本，长度应在 8-128 位之间"
    )
    nickname: Optional[str] = Field(
        None, 
        min_length=1, 
        max_length=50, 
        description="用户展示昵称（选填）"
    )

class LoginRequest(BaseSchema):
    """
    手机号+密码登录请求体
    """
    phone: str = Field(..., description="登录手机号")
    password: str = Field(..., description="密码原内文")

class LoginResponse(BaseSchema):
    """
    登录成功返回的包装结构
    """
    access_token: str = Field(..., description="颁发的 JWT Token 字符串")
    token_type: str = Field(default="bearer", description="Token 鉴权类型")
    expires_in: int = Field(..., description="剩余有效秒数")
