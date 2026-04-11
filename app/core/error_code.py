"""
File: app/core/error_code.py
Description: 全局错误码基类与系统级错误定义

本模块定义了错误码的枚举基类及系统通用的错误状态。
遵循 v2.1 现代电商架构规范：语义化 HTTP 状态码 + 字符串命名空间。

定义结构 Tuple(http_status, code, message):
1. http_status: HTTP 响应状态码 (4xx/5xx)
2. code: 字符串业务码 (格式: domain.reason)
3. message: 默认的人类可读错误消息

Author: jinmozhe
Created: 2026-01-15
"""

from enum import Enum

from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_500_INTERNAL_SERVER_ERROR,
)


class BaseErrorCode(Enum):
    """
    错误码枚举基类
    所有业务领域的错误码 Enum 必须继承此类。

    Value Tuple Definition:
    (http_status, code, msg)
    """

    @property
    def http_status(self) -> int:
        """获取映射的 HTTP 状态码"""
        return self.value[0]

    @property
    def code(self) -> str:
        """获取业务错误标识 (domain.reason)"""
        return self.value[1]

    @property
    def msg(self) -> str:
        """获取默认错误描述信息"""
        return self.value[2]


class SystemErrorCode(BaseErrorCode):
    """
    系统通用错误定义 (System Domain)
    包含: 参数校验、认证基础、系统故障
    """

    # HTTP 400: 客户端参数错误 (Pydantic 校验会自动映射到这里)
    INVALID_PARAMS = (HTTP_400_BAD_REQUEST, "system.invalid_params", "参数校验失败")

    # HTTP 401: 身份认证失败 (通常由网关或中间件拦截)
    UNAUTHORIZED = (HTTP_401_UNAUTHORIZED, "system.unauthorized", "身份认证失败")
    TOKEN_EXPIRED = (HTTP_401_UNAUTHORIZED, "system.token_expired", "令牌已过期")

    # HTTP 403: 权限/禁止访问 (通用)
    FORBIDDEN = (HTTP_403_FORBIDDEN, "system.forbidden", "权限不足")

    # HTTP 500: 服务端故障 (需要监控报警)
    INTERNAL_ERROR = (
        HTTP_500_INTERNAL_SERVER_ERROR,
        "system.internal_error",
        "系统内部错误",
    )
    DB_ERROR = (HTTP_500_INTERNAL_SERVER_ERROR, "system.db_error", "数据库操作异常")
