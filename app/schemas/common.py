from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

class BaseSchema(BaseModel):
    """
    项目中所有 Schema 的基础类
    开启了 from_attributes = True 支持从 ORM 对象隐式构建
    """
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class ApiResponse(BaseModel, Generic[T]):
    """
    符合《01_后端全局约束与命名规范》的标准响应体
    """
    code: int = Field(default=20000, description="业务状态码")
    message: str = Field(default="success", description="提示信息内容")
    data: Optional[T] = Field(default=None, description="核心业务数据")
    trace_id: Optional[str] = Field(default=None, description="请求追踪流水号")

class ErrorResponse(BaseModel):
    """
    用于 4xx, 5xx 请求失败情形的全局统一错误返回结构
    与 ApiResponse 保持高度一致的风格
    """
    code: int = Field(..., description="业务内部错误码")
    message: str = Field(..., description="错误详细提示内容")
    data: Optional[Any] = Field(default=None, description="附加错误信息，通常为 null")
    trace_id: Optional[str] = Field(default=None, description="请求追踪流水号")
