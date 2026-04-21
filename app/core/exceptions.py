from typing import Any, Dict, Optional
from fastapi import HTTPException


class ErrorResponseAPIException(HTTPException):
    """
    统一自定义异常基类
    封装项目规范：返回携带内部 code 及附带数据的 4xx / 5xx 响应
    """
    def __init__(
        self,
        status_code: int,
        detail: Any = None,
        code: int = 40000,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


class CredentialsException(ErrorResponseAPIException):
    def __init__(self, detail: str = "Token 验证失败或已过期"):
        super().__init__(
            status_code=401,
            detail=detail,
            code=40102,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(ErrorResponseAPIException):
    def __init__(self, detail: str = "越权操作：无权访问指定资源"):
        super().__init__(
            status_code=403,
            detail=detail,
            code=40301,
        )


class NotFoundException(ErrorResponseAPIException):
    def __init__(self, detail: str = "资源不存在"):
        super().__init__(
            status_code=404,
            detail=detail,
            code=40401,
        )


class ConflictException(ErrorResponseAPIException):
    def __init__(self, detail: str = "资源发生冲突"):
        super().__init__(
            status_code=409,
            detail=detail,
            code=40901,
        )
