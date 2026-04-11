"""
File: app/core/response.py
Description: 统一响应信封（Unified Response Envelope）模型与辅助函数

本模块定义了全站统一的 API 响应格式。
所有 HTTP 接口必须遵循此契约返回数据。

Author: jinmozhe
Created: 2025-11-24
Updated: 2026-02-01 (v2.3: Fix Pylance static analysis errors)
"""

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ResponseBase(BaseModel):
    """
    响应基类
    """

    model_config = ConfigDict(from_attributes=True)

    code: str = Field(default="success", description="业务状态码")
    message: str = Field(default="Success", description="响应消息")
    request_id: str | None = Field(default=None, description="请求追踪ID")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="响应生成时间",
    )


class ResponseModel(ResponseBase, Generic[T]):
    """
    统一响应信封
    """

    data: T | None = Field(default=None, description="业务数据")

    @classmethod
    def success(
        cls,
        data: T | None = None,
        message: str = "Success",
        request_id: str | None = None,
    ) -> "ResponseModel[T]":
        """
        构造成功响应
        """
        # [Standard Update] 防御性编码：强制将 Pydantic 模型转换为 JSON 安全的字典
        # 使用 cast(Any, data) 解决 Pylance 报错:
        # "Cannot access member 'model_dump' for type 'object*'"
        if hasattr(data, "model_dump"):
            data = cast(Any, data).model_dump(mode="json")

        return cls(
            code="success",
            message=message,
            data=data,
            request_id=request_id,
        )

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        data: Any = None,
        request_id: str | None = None,
    ) -> "ResponseModel[Any]":
        """
        构造失败响应
        """
        return cls(
            code=code,
            message=message,
            data=data,
            request_id=request_id,
        )
