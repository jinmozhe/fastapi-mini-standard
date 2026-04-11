"""
File: app/domains/admin/router.py
Description: B端管理员领域 HTTP 路由层

定义 B 端管理员认证相关的 API 端点：
  POST /api/v1/admin/login   → 管理员登录，返回双 Token
  POST /api/v1/admin/refresh → 管理员 Token 刷新（旋转策略）
  POST /api/v1/admin/logout  → 管理员登出
  GET  /api/v1/admin/me      → 获取当前管理员信息 + 角色权限树（供 React 渲染菜单）

规范：
  - 使用统一响应信封 (ResponseModel.success)
  - AdminAuthServiceDep 进行服务注入
  - 引用 AdminMsg 常量作为响应消息
  - 完整的 OpenAPI 文档描述

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis

from app.api.deps import CurrentAdmin, DBSession
from app.core.redis import get_redis
from app.core.rate_limit import RateLimiter
from app.core.response import ResponseModel
from app.domains.admin.constants import AdminMsg
from app.domains.admin.repository import AdminRepository
from app.domains.admin.schemas import (
    AdminLoginRequest,
    AdminLogoutRequest,
    AdminMe,
    AdminRefreshRequest,
    AdminToken,
)
from app.domains.admin.service import AdminAuthService

router = APIRouter()

# ------------------------------------------------------------------------------
# 依赖注入构造器
# ------------------------------------------------------------------------------


async def get_admin_service(
    session: DBSession,
    redis: Annotated[Redis, Depends(get_redis)],
) -> AdminAuthService:
    """
    构建 AdminAuthService 实例，注入 session 与 redis。
    """
    admin_repo = AdminRepository(session=session)
    return AdminAuthService(admin_repo=admin_repo, redis=redis)


AdminAuthServiceDep = Annotated[AdminAuthService, Depends(get_admin_service)]


# ------------------------------------------------------------------------------
# 路由定义
# ------------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=ResponseModel[AdminToken],
    summary="管理员登录",
    description=(
        "B端管理员通过用户名+密码登录，返回带 `aud=backend` 区分标识的双 Token。\n\n"
        "接口已挂载滑动窗口限流 (10次/60秒)，防止暴力拆解管理员密码。"
    ),
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
)
async def admin_login(
    body: AdminLoginRequest,
    request: Request,
    service: AdminAuthServiceDep,
) -> ResponseModel[AdminToken]:
    """管理员登录端点。"""
    ip_address = request.headers.get(
        "X-Forwarded-For",
        request.client.host if request.client else None,
    )
    user_agent = request.headers.get("User-Agent")

    token = await service.login(
        username=body.username,
        password=body.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return ResponseModel.success(data=token, message=AdminMsg.LOGIN_SUCCESS)


@router.post(
    "/refresh",
    response_model=ResponseModel[AdminToken],
    summary="管理员令牌刷新",
    description=(
        "使用 Refresh Token 换取新的双 Token。\n\n"
        "采用 Redis RENAME 原子操作消费旧 Token 防止重放。B端与C端会话完全隔离。"
    ),
)
async def admin_refresh(
    body: AdminRefreshRequest,
    service: AdminAuthServiceDep,
) -> ResponseModel[AdminToken]:
    """管理员令牌刷新端点。"""
    token = await service.refresh_token(refresh_token=body.refresh_token)
    return ResponseModel.success(data=token, message=AdminMsg.REFRESH_SUCCESS)


@router.post(
    "/logout",
    response_model=ResponseModel[None],
    summary="管理员登出",
    description="销毁 Refresh Token 及其关联的 B端会话族谱，强制注销该设备登录态。",
)
async def admin_logout(
    body: AdminLogoutRequest,
    service: AdminAuthServiceDep,
) -> ResponseModel[None]:
    """管理员登出端点。"""
    await service.logout(refresh_token=body.refresh_token)
    return ResponseModel.success(data=None, message=AdminMsg.LOGOUT_SUCCESS)


@router.get(
    "/me",
    response_model=ResponseModel[AdminMe],
    summary="获取当前管理员信息",
    description=(
        "返回当前登录管理员的基本信息、角色列表与权限码集合。\n\n"
        "React 等前端框架调用此接口，根据 `permissions` 数组动态渲染侧边栏菜单与按钮显隐。\n\n"
        "权限码格式约定：`{模块}:{动作}`，例如 `order:view`、`order:refund`、`finance:export`。"
    ),
)
async def admin_me(
    admin: CurrentAdmin,
    session: DBSession,
) -> ResponseModel[AdminMe]:
    """
    获取管理员自身信息 + 角色权限树（供前端动态路由使用）。
    CurrentAdmin 依赖已在 deps.py 中预加载角色与权限，可直接序列化返回。
    """
    return ResponseModel.success(
        data=AdminMe.model_validate(admin),
        message=AdminMsg.ME_SUCCESS,
    )
