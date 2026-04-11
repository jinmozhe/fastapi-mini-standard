"""
File: app/domains/auth/service.py
Description: 认证领域服务 (Service)

本模块封装认证核心业务逻辑：
1. 登录校验: 验证手机号与密码，签发双 Token。
2. 刷新令牌: 验证 Redis 中的 Refresh Token，执行旋转策略 (Rotation)。
3. 用户登出: 销毁 Refresh Token。
4. 依赖注入: 依赖 UserRepository (查用户) 和 Redis (存 Token)。

Author: jinmozhe
Created: 2025-12-05
Updated: 2026-01-15 (v2.1: Adapt to new Exception & ErrorCode standards)
"""

import secrets
from datetime import timedelta

from redis.asyncio import Redis

from app.core.config import settings
from app.core.error_code import SystemErrorCode
from app.core.exceptions import AppException
from app.core.logging import logger
from app.core.security import (
    create_access_token,
    get_password_hash_async,
    verify_password_async,
)
from app.db.models.user import User
from app.domains.auth.constants import AuthError
from app.domains.auth.schemas import LoginRequest, RegisterRequest, Token
from app.domains.users.repository import UserRepository


class AuthService:
    """
    认证服务类。
    """

    def __init__(self, user_repo: UserRepository, redis: Redis):
        self.user_repo = user_repo
        self.redis = redis

    async def register(self, reg_data: RegisterRequest) -> Token:
        """
        用户注册流程。

        流程:
        1. 唯一性校验 (Fail Fast)：手机号、邮箱、用户名
        2. 密码哈希 (异步)
        3. 创建用户并持久化
        4. 生成双 Token (自动登录)
        """
        # 1. 唯一性校验
        if await self.user_repo.get_by_phone_number(reg_data.phone_number):
            raise AppException(AuthError.PHONE_EXIST)

        if reg_data.email and await self.user_repo.get_by_email(reg_data.email):
            raise AppException(AuthError.EMAIL_EXIST)

        if reg_data.username and await self.user_repo.get_by_username(
            reg_data.username
        ):
            raise AppException(AuthError.USERNAME_EXIST)

        # 2. 密码哈希
        hashed_password = await get_password_hash_async(reg_data.password)

        # 3. 创建用户
        user = User(
            phone_number=reg_data.phone_number,
            hashed_password=hashed_password,
            username=reg_data.username,
            email=reg_data.email,
        )

        # 4. 持久化
        self.user_repo.session.add(user)
        await self.user_repo.session.flush()
        await self.user_repo.session.commit()
        await self.user_repo.session.refresh(user)

        logger.bind(user_id=str(user.id), phone_number=user.phone_number).info(
            "User registered successfully"
        )

        # 5. 自动生成 Token (注册后自动登录)
        return await self._create_tokens(user_id=str(user.id))

    async def login(
        self, login_data: LoginRequest, ip_address: str | None = None, user_agent: str | None = None
    ) -> Token:
        """
        用户登录流程。

        流程:
        1. 查库获取用户 (Fail Fast)
        2. 验证密码哈希 (异步)
        3. 检查用户激活状态
        4. 生成 Access Token (JWT) + Refresh Token (Redis)
        5. 记录 LoginLog
        """
        
        user_id_for_log = ""
        status = False
        reason = ""
        
        try:
            # 1. 查询用户
            user = await self.user_repo.get_by_phone_number(login_data.phone_number)
            if not user:
                reason = "账号或密码错误"
                raise AppException(AuthError.INVALID_CREDENTIALS)

            user_id_for_log = str(user.id)

            # 2. 校验密码
            if not await verify_password_async(login_data.password, user.hashed_password):
                reason = "账号或密码错误"
                raise AppException(AuthError.INVALID_CREDENTIALS)

            # 3. 检查状态
            if not user.is_active:
                reason = "用户处于未激活/封禁状态"
                raise AppException(AuthError.ACCOUNT_LOCKED)

            status = True
            reason = "登录成功"
            
            # 4. 签发令牌
            return await self._create_tokens(user_id=str(user.id))
            
        except AppException as e:
            raise e
        finally:
            # 5. 无论成功失败，都记录登录日志
            # TODO: 待 LoginLog 模型实现后，改为 ORM 持久化
            logger.bind(
                user_id=user_id_for_log if user_id_for_log else "Unknown",
                login_ip=ip_address,
                user_agent=user_agent,
                status=status,
                reason=reason,
            ).info("Login attempt recorded")

    async def refresh_token(self, refresh_token: str) -> Token:
        """
        使用 Refresh Token 换取新 Token (Token Rotation)。

        流程:
        1. 查 Redis 确认 token 有效性
        2. 若无效/过期，抛出 401
        3. 销毁旧 Token (防重放)
        4. 签发全新的一对 Access + Refresh Token
        """
        redis_key = f"refresh_token:{refresh_token}"
        user_id = await self.redis.get(redis_key)

        if not user_id:
            # Token 无效属于系统级认证失败，使用 SystemErrorCode.UNAUTHORIZED (HTTP 401)
            # 这里选择覆盖默认 message，提供更具体的上下文
            raise AppException(
                SystemErrorCode.UNAUTHORIZED, message="Refresh token 无效或已过期"
            )

        # 可选：此处可加一步查库，确保用户未被封号/软删除
        # user = await self.user_repo.get(user_id) ...

        # 销毁旧 Token (一次性使用策略)
        await self.redis.delete(redis_key)

        # 签发新 Token
        return await self._create_tokens(user_id=user_id)

    async def logout(self, refresh_token: str) -> None:
        """
        用户登出。
        直接从 Redis 删除对应的 Refresh Token。
        """
        redis_key = f"refresh_token:{refresh_token}"
        await self.redis.delete(redis_key)

    async def _create_tokens(self, user_id: str) -> Token:
        """
        [内部方法] 构造 Token 响应并持久化 Refresh Token。
        """
        # 1. 生成 Access Token (JWT)
        access_token = create_access_token(subject=user_id)

        # 2. 生成 Refresh Token (高熵随机串)
        # 使用 urlsafe_token_hex 生成 32 字节 (约 43 字符) 的随机串
        refresh_token = secrets.token_urlsafe(32)

        # 3. 存入 Redis
        # Key: refresh_token:xyz... -> Value: user_id
        # 设置过期时间 (例如 7 天)
        await self.redis.setex(
            f"refresh_token:{refresh_token}",
            timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_id,
        )

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            token_type="bearer",
        )
