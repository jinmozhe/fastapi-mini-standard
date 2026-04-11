"""
File: app/main.py
Description: FastAPI 应用入口与工厂函数

本模块负责：
1. 创建 FastAPI 应用实例 (设置默认响应类为 ORJSONResponse)
2. 管理应用生命周期 (lifespan): 启动日志、关闭数据库与Redis连接
3. 组装全局组件：中间件、异常处理器、路由
4. 提供健康检查接口 (/pinjie/health)

Author: jinmozhe
Created: 2025-12-05
Updated: 2026-01-15 (v2.1: Health check aligns with Unified Response)
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles

from app.api_router import api_router
from app.core.config import settings

# 直接导入封装好的注册函数
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import register_middlewares
from app.core.redis import close_redis

# [新增] 导入统一响应模型
from app.core.response import ResponseModel
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理器 (FastAPI 0.93+ 推荐方式)。
    """
    # 1. 启动时：初始化日志系统
    setup_logging()

    yield

    # 2. 关闭时：优雅释放资源
    # 关闭 Redis 连接池
    await close_redis()
    # 关闭数据库连接池
    await engine.dispose()


def create_app() -> FastAPI:
    """应用工厂函数"""

    # 定义混淆前缀 (策略 B)
    obscure_prefix = "/pinjie"

    app = FastAPI(
        title=settings.PROJECT_NAME,
        # 混淆 OpenAPI Schema JSON 路径
        openapi_url=f"{obscure_prefix}/openapi.json",
        # 强制默认响应类为 ORJSONResponse (高性能)
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        # 混淆 Swagger UI 文档路径
        docs_url=f"{obscure_prefix}/docs",
        # 关闭默认 ReDoc，手动接管
        redoc_url=None,
    )

    # 挂载静态文件目录 (ReDoc 本地化资源)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # 自定义 ReDoc 路由 (极简本地化版)
    @app.get(f"{obscure_prefix}/redoc", include_in_schema=False)
    async def redoc_html():
        """
        自定义 ReDoc 文档页面。
        - JS/Favicon: 使用本地资源 (快且稳)
        - Fonts: 禁用 Google Fonts，直接使用系统字体 (最快)
        """
        return get_redoc_html(
            openapi_url=f"{obscure_prefix}/openapi.json",
            title=f"{settings.PROJECT_NAME} - ReDoc",
            redoc_js_url="/static/redoc.standalone.js",
            redoc_favicon_url="/static/favicon.png",
            with_google_fonts=False,
        )

    # 1. 注册中间件 (CORS, RequestID, Logging)
    register_middlewares(app)

    # 2. 注册异常处理器 (直接调用导入的函数)
    # 注意：app/core/exceptions.py 更新后，此函数依然可用且逻辑已更新
    register_exception_handlers(app)

    # 3. 挂载 API 路由
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # 4. 挂载健康检查
    # [变更] 返回类型改为 ResponseModel，保持全站响应结构一致
    @app.get(
        f"{obscure_prefix}/health",
        tags=["health"],
        summary="健康检查",
        response_model=ResponseModel[dict[str, str]],
    )
    async def health_check():
        """
        健康检查接口。
        用于 K8s Liveness/Readiness Probe 或负载均衡器检查。
        返回统一响应信封。
        """
        return ResponseModel.success(data={"status": "ok"})

    return app


# 暴露给 Uvicorn 运行的应用实例
app = create_app()

if __name__ == "__main__":
    # 本地调试入口
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
