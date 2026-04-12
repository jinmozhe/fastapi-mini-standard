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
from app.core.sms import send_sms_code
from app.db.models.sms_log import SmsLog
from app.db.models.user import User
from app.db.models.user_social import UserSocial

from app.domains.auth.constants import AuthMsg
from app.domains.auth.repository import SmsLogRepository, UserSocialRepository
from app.domains.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    SmsCodeRequest,
    SmsLoginRequest,
    Token,
    WechatLoginRequest,
)
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
    自动注入数据库会话 (Session)、Redis 客户端和社交绑定仓储。
    """
    user_repo = UserRepository(model=User, session=session)
    social_repo = UserSocialRepository(model=UserSocial, session=session)
    return AuthService(user_repo=user_repo, redis=redis, social_repo=social_repo)


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

    return ResponseModel.success(
        data=None, message=AuthMsg.LOGOUT_SUCCESS, request_id=req_id
    )


# ------------------------------------------------------------------------------
# 多渠道登录接口 (SMS + 微信小程序)
# ------------------------------------------------------------------------------


@router.post(
    "/sms/send",
    response_model=ResponseModel[None],
    summary="发送短信验证码",
    description=(
        "向指定手机号发送登录验证码。同一手机号 60 秒内只能发送一次，"
        "验证码有效期 5 分钟。\n\n"
        "开发环境 (SMS_ENABLE=False) 下不会实际发送，验证码固定为 888888。"
    ),
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
)
async def send_sms_code_endpoint(
    request: Request,
    sms_data: SmsCodeRequest,
    session: DBSession,
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseModel[None]:
    """发送短信验证码"""
    ip_address = request.client.host if request.client else None

    # 发送验证码
    code = await send_sms_code(
        redis=redis,
        phone_code=sms_data.phone_code,
        mobile=sms_data.mobile,
        sms_type="login",
        ip_address=ip_address,
    )

    # 记录短信发送日志 (审计铁账本)
    from app.core.config import settings
    sms_log = SmsLog(
        phone_code=sms_data.phone_code,
        mobile=sms_data.mobile,
        sms_type="login",
        status="success",
        provider="tencent",
        template_id=settings.SMS_TEMPLATE_LOGIN or None,
        ip_address=ip_address,
    )
    sms_log_repo = SmsLogRepository(session=session)
    await sms_log_repo.create(sms_log)
    await session.commit()

    req_id = getattr(request.state, "request_id", None)
    return ResponseModel.success(
        data=None, message=AuthMsg.SMS_SEND_SUCCESS, request_id=req_id
    )


@router.post(
    "/sms/login",
    response_model=ResponseModel[Token],
    summary="短信验证码登录 (注册即登录)",
    description=(
        "使用手机号和短信验证码登录。如果该手机号尚未注册，系统将自动创建账号。\n\n"
        "可选传入 `inviter_id`，用于建立推荐关系（仅新注册时生效）。"
    ),
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
)
async def sms_login(
    request: Request,
    login_data: SmsLoginRequest,
    service: AuthServiceDep,
) -> ResponseModel[Token]:
    """短信验证码登录 (注册即登录)"""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    token = await service.sms_login(
        login_data, ip_address=ip_address, user_agent=user_agent
    )

    req_id = getattr(request.state, "request_id", None)
    return ResponseModel.success(
        data=token, message=AuthMsg.SMS_LOGIN_SUCCESS, request_id=req_id
    )


@router.post(
    "/wechat/login",
    response_model=ResponseModel[Token],
    summary="微信小程序授权登录",
    description=(
        "通过微信小程序授权登录。\n\n"
        "前端需调用 `wx.login()` 获取 `js_code`，"
        "调用 `wx.getPhoneNumber()` 获取加密手机号数据。\n\n"
        "后端解密后以手机号为唯一身份锚点进行合流或注册。"
    ),
)
async def wechat_login(
    request: Request,
    login_data: WechatLoginRequest,
    service: AuthServiceDep,
) -> ResponseModel[Token]:
    """微信小程序授权登录"""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    token = await service.wechat_login(
        login_data, ip_address=ip_address, user_agent=user_agent
    )

    req_id = getattr(request.state, "request_id", None)
    return ResponseModel.success(
        data=token, message=AuthMsg.WECHAT_LOGIN_SUCCESS, request_id=req_id
    )
