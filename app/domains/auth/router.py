"""
File: app/domains/auth/router.py
Description: 认证领域 HTTP 路由层

本模块定义认证相关的 API 端点：
1. POST /login: 登录 (返回双 Token)
2. POST /refresh: 刷新 (旋转策略，返回新双 Token)
3. POST /logout: 登出 (销毁 Refresh Token)

规范：
- 使用统一响应信封 (ResponseModel.success)
- 使用 AuthServiceDep 进行服务注入
- 引用 AuthMsg 常量作为响应消息
- 完整的 OpenAPI 文档描述

Author: jinmozhe
Created: 2025-12-05
Updated: 2026-01-15 (v2.1: Adapt to Unified Response & AuthMsg constants)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis

from app.api.deps import DBSession
from app.core.redis import get_redis
from app.core.rate_limit import RateLimiter

# [变更] 仅导入 ResponseModel，移除 success 辅助函数
from app.core.response import ResponseModel
from app.db.models.user import User

# [变更] 导入领域消息常量
from app.domains.auth.constants import AuthMsg
from app.domains.auth.schemas import LoginRequest, RefreshRequest, RegisterRequest, Token
from app.domains.auth.service import AuthService
from app.domains.users.repository import UserRepository

router = APIRouter()

# ------------------------------------------------------------------------------
# 依赖注入构造器 (Dependencies)
# ------------------------------------------------------------------------------


async def get_auth_service(
    session: DBSession,
    redis: Annotated[Redis, Depends(get_redis)],
) -> AuthService:
    """
    构造 AuthService 实例。
    自动注入数据库会话 (Session) 和 Redis 客户端。
    """
    # 复用 User 领域的 Repository
    user_repo = UserRepository(model=User, session=session)
    return AuthService(user_repo=user_repo, redis=redis)


# 类型别名：Auth 服务依赖
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


# ------------------------------------------------------------------------------
# Endpoints (路由定义)
# ------------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=ResponseModel[Token],
    status_code=201,
    summary="用户注册",
    description="创建新用户账户。提供手机号和密码即可注册。成功后返回访问令牌，自动登录状态。",
)
async def register(
    request: Request,
    reg_data: RegisterRequest,
    service: AuthServiceDep,
) -> ResponseModel[Token]:
    """
    注册接口 (Public)
    """
    token = await service.register(reg_data)
    req_id = getattr(request.state, "request_id", None)

    return ResponseModel.success(
        data=token, message=AuthMsg.REGISTER_SUCCESS, request_id=req_id
    )

@router.post(
    "/login",
    response_model=ResponseModel[Token],
    summary="用户登录",
    description="使用手机号密码登录，成功后返回 Access Token (JWT) 和 Refresh Token。",
    dependencies=[Depends(RateLimiter(times=5, seconds=60))]
)
async def login(
    request: Request,
    login_data: LoginRequest,
    service: AuthServiceDep,
) -> ResponseModel[Token]:
    """
    登录接口
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    token = await service.login(login_data, ip_address=ip_address, user_agent=user_agent)
    req_id = getattr(request.state, "request_id", None)

    # [变更] 使用 ResponseModel.success + AuthMsg
    return ResponseModel.success(
        data=token, message=AuthMsg.LOGIN_SUCCESS, request_id=req_id
    )


@router.post(
    "/refresh",
    response_model=ResponseModel[Token],
    summary="刷新令牌 (续期)",
    description="使用有效的 Refresh Token 换取新的一对 Token (Token Rotation 策略)。旧 Token 将失效。",
)
async def refresh_token(
    request: Request,
    refresh_data: RefreshRequest,
    service: AuthServiceDep,
) -> ResponseModel[Token]:
    """
    刷新 Token 接口
    """
    token = await service.refresh_token(refresh_data.refresh_token)
    req_id = getattr(request.state, "request_id", None)

    # [变更] 使用 ResponseModel.success + AuthMsg
    return ResponseModel.success(
        data=token, message=AuthMsg.REFRESH_SUCCESS, request_id=req_id
    )


@router.post(
    "/logout",
    response_model=ResponseModel[None],
    summary="用户登出",
    description="销毁服务端存储的 Refresh Token，使该会话失效。",
)
async def logout(
    request: Request,
    refresh_data: RefreshRequest,
    service: AuthServiceDep,
) -> ResponseModel[None]:
    """
    登出接口
    """
    await service.logout(refresh_data.refresh_token)
    req_id = getattr(request.state, "request_id", None)

    # [变更] 使用 ResponseModel.success + AuthMsg
    return ResponseModel.success(
        data=None, message=AuthMsg.LOGOUT_SUCCESS, request_id=req_id
    )
