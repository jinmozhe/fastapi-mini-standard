"""
File: app/core/exceptions.py
Description: 业务异常类与全局异常处理器

本模块遵循 v2.1 架构规范：
1. 业务异常基类（AppException）接受 BaseErrorCode 枚举
2. 全局异常处理器自动将异常映射为：语义化 HTTP 状态码 + 字符串业务码
3. 使用 ResponseModel.fail() 构造统一的失败响应信封

Author: jinmozhe
Created: 2025-11-24
Updated: 2026-01-15 (v2.1 Modern Standard)
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.error_code import BaseErrorCode, SystemErrorCode
from app.core.logging import logger
from app.core.response import ResponseModel

# ------------------------------------------------------------------------------
# 1. 自定义业务异常类
# ------------------------------------------------------------------------------


class AppException(Exception):
    """
    应用基础异常类。

    用法示例:
        raise AppException(AuthError.PASSWORD_ERROR)
        raise AppException(OrderError.STOCK_NOT_ENOUGH, message="库存仅剩1件")
    """

    def __init__(
        self,
        error: BaseErrorCode,
        message: str = "",
        data: Any = None,
    ):
        # 自动从枚举中解构: (HTTP状态, 业务码, 默认文案)
        self.http_status = error.http_status
        self.code = error.code
        self.message = message or error.msg
        self.data = data
        super().__init__(self.message)


# ------------------------------------------------------------------------------
# 2. 辅助函数
# ------------------------------------------------------------------------------


def _get_request_id(request: Request) -> str:
    """尝试从 request.state 获取 request_id，如果不存在则返回 'unknown'"""
    return str(getattr(request.state, "request_id", "unknown"))


# ------------------------------------------------------------------------------
# 3. 全局异常处理器 (Handlers)
# ------------------------------------------------------------------------------


async def app_exception_handler(request: Request, exc: AppException) -> ORJSONResponse:
    """
    处理自定义业务异常 (AppException)
    直接映射为定义好的 HTTP 状态码和 Code
    """
    request_id = _get_request_id(request)

    # 业务警告日志 (通常不需要 stack trace)
    logger.bind(
        request_id=request_id,
        code=exc.code,
        http_status=exc.http_status,
        message=exc.message,
    ).warning("Business exception occurred")

    # [变更] 使用类方法 ResponseModel.fail
    response_model = ResponseModel.fail(
        code=exc.code,
        message=exc.message,
        data=exc.data,
        request_id=request_id,
    )

    return ORJSONResponse(
        status_code=exc.http_status,
        content=response_model.model_dump(),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> ORJSONResponse:
    """
    处理 Pydantic 校验异常 (FastAPI 默认抛出 422)
    映射目标: HTTP 400 Bad Request / Code: system.invalid_params
    """
    request_id = _get_request_id(request)

    errors = exc.errors()
    first_error = errors[0] if errors else {}

    # 获取出错字段路径: body -> email
    # loc 示例: ('body', 'email')
    loc = first_error.get("loc", [])
    field_name = str(loc[-1]) if loc else "unknown"
    msg = first_error.get("msg", "Invalid parameter")

    # 组合成人类可读的消息
    readable_message = f"{field_name}: {msg}"

    logger.bind(
        request_id=request_id,
        detail=readable_message,
        raw_errors=errors,
    ).warning("Request validation failed")

    # [变更] 使用类方法 ResponseModel.fail
    # 将原始错误详情放入 data 以便前端调试 (可选)
    response_model = ResponseModel.fail(
        code=SystemErrorCode.INVALID_PARAMS.code,
        message=readable_message,
        data={"errors": errors},
        request_id=request_id,
    )

    return ORJSONResponse(
        status_code=SystemErrorCode.INVALID_PARAMS.http_status,
        content=response_model.model_dump(),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> ORJSONResponse:
    """
    处理框架层面的 HTTP 异常 (如 404 Not Found, 405 Method Not Allowed)
    """
    request_id = _get_request_id(request)

    # 构造一个通用的系统错误码
    # 如果是 404，通常意味着路由没匹配到
    code_str = "system.not_found" if exc.status_code == 404 else "system.http_error"

    logger.bind(
        request_id=request_id,
        status_code=exc.status_code,
        detail=str(exc.detail),
    ).warning("Framework HTTP exception occurred")

    # [变更] 使用类方法 ResponseModel.fail
    response_model = ResponseModel.fail(
        code=code_str,
        message=str(exc.detail),
        request_id=request_id,
    )

    return ORJSONResponse(
        status_code=exc.status_code,
        content=response_model.model_dump(),
    )


async def general_exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
    """
    处理所有未捕获的异常 (500 Internal Server Error)
    这是最后的防线，防止服务器崩溃信息直接暴露给用户
    """
    request_id = _get_request_id(request)

    # 记录完整堆栈信息 (Error Level)
    logger.opt(exception=exc).bind(request_id=request_id).error(
        "Unhandled system exception occurred"
    )

    # [变更] 使用类方法 ResponseModel.fail
    # 屏蔽内部细节，返回通用系统错误
    response_model = ResponseModel.fail(
        code=SystemErrorCode.INTERNAL_ERROR.code,
        message=SystemErrorCode.INTERNAL_ERROR.msg,
        request_id=request_id,
    )

    return ORJSONResponse(
        status_code=SystemErrorCode.INTERNAL_ERROR.http_status,
        content=response_model.model_dump(),
    )


# ------------------------------------------------------------------------------
# 4. 异常处理器注册函数
# ------------------------------------------------------------------------------


def register_exception_handlers(app: FastAPI) -> None:
    """
    统一注册所有异常处理器。
    应在 main.py 中调用。
    """
    # 捕获自定义业务异常
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore

    # 捕获参数校验异常 (Override FastAPI default 422)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore

    # 捕获 HTTP 协议异常 (404, 405 etc.)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore

    # 捕获所有未处理的系统异常 (500)
    app.add_exception_handler(Exception, general_exception_handler)
