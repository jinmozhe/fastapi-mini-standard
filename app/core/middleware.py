"""
File: app/core/middleware.py
Description: 中间件配置与实现

本模块负责：
1. 定义 RequestLogMiddleware：
   - 生成 UUID v7 request_id
   - 绑定 Loguru 上下文
   - 记录访问日志 (Access Log)
   - 添加 X-Request-ID 响应头
2. 提供 register_middlewares 函数：
   - 统一注册 CORS、RequestLogMiddleware 等

Author: jinmozhe
Created: 2025-11-24
"""

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from uuid6 import uuid7

from app.core.config import settings
from app.core.logging import logger

# 跳过详细日志的路径（健康检查等高频低价值请求）
SKIP_LOG_PATHS: set[str] = {"/health", "/health/", "/metrics", "/favicon.ico"}


class RequestLogMiddleware(BaseHTTPMiddleware):
    """
    全局请求日志中间件

    职责：
    1. 为每个请求生成唯一 Request ID (UUID v7)
    2. 将 request_id 绑定到 Loguru 上下文，贯穿整个请求链路
    3. 记录请求处理耗时与最终状态码
    4. 在响应头中回传 X-Request-ID
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # 1. 生成 Request ID (UUID v7)
        request_id = str(uuid7())

        # 2. 绑定到 request.state 供应用内部使用 (如异常处理器)
        request.state.request_id = request_id

        # 判断是否跳过详细日志
        skip_log = request.url.path in SKIP_LOG_PATHS

        # 3. 开启 Loguru 上下文 (Scope)
        # 注意：在此 with 块内，Router/Service/Repo 产生的所有日志都会自动携带 request_id
        with logger.contextualize(request_id=request_id):
            start_time = time.perf_counter()

            try:
                # 执行后续中间件及路由处理
                response = await call_next(request)
                # 4. 添加响应头 X-Request-ID
                response.headers["X-Request-ID"] = request_id

                # 5. 记录 Access Log（跳过健康检查等路径）
                if not skip_log:
                    # 计算耗时 (ms)
                    process_time = (time.perf_counter() - start_time) * 1000
                    # 即使是业务异常，经过 ExceptionHandler 处理后也会返回 Response，因此通常会走到这里。
                    logger.bind(
                        method=request.method,
                        path=request.url.path,
                        status_code=response.status_code,
                        duration_ms=round(process_time, 2),
                        client_ip=request.client.host if request.client else "unknown",
                        user_agent=request.headers.get("user-agent", ""),
                    ).info("Request finished")

                return response

            except Exception as exc:
                # 异常始终记录，不跳过
                # 理论上，FastAPI 的 ExceptionHandler 会捕获大部分异常并返回 Response。
                # 如果代码走到这里，说明发生了中间件层面的严重错误或 Handler 未捕获的异常。
                process_time = (time.perf_counter() - start_time) * 1000
                # 记录完整异常堆栈
                logger.bind(
                    method=request.method,
                    path=request.url.path,
                    duration_ms=round(process_time, 2),
                ).opt(exception=exc).error("Request failed with unhandled exception")

                # 使用不带参数的 raise 以保留原始 traceback
                raise


def register_middlewares(app: FastAPI) -> None:
    """
    统一注册所有中间件。
    注意：FastAPI/Starlette 中间件执行顺序是"洋葱模型"，
    后注册的中间件先执行 (对于请求进入方向)。
    """
    # 1. CORS (跨域资源共享)
    # 必须配置，否则前端无法调用
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            # 将 Pydantic 的 AnyHttpUrl 转换为字符串
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # 2. Audit Log（B端管理员操作审计，拦截 /admin/ 写操作并旁路落库）
    from app.core.audit import AuditLogMiddleware
    app.add_middleware(AuditLogMiddleware)

    # 3. Request Log & ID (建议最后注册，以便最先拦截请求并注入 request_id)
    app.add_middleware(RequestLogMiddleware)
