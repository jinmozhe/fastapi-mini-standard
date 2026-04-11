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
from redis.exceptions import ResponseError
from uuid6 import uuid7

from app.core.config import settings
from app.core.error_code import SystemErrorCode
from app.core.exceptions import AppException
from app.core.logging import logger
from app.core.captcha import verify_captcha_async
from app.db.models.log import LoginLog
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
        if await self.user_repo.get_by_mobile(reg_data.phone_code, reg_data.mobile):
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
            phone_code=reg_data.phone_code,
            mobile=reg_data.mobile,
            hashed_password=hashed_password,
            username=reg_data.username,
            email=reg_data.email,
        )

        # 4. 持久化
        self.user_repo.session.add(user)
        await self.user_repo.session.flush()
        await self.user_repo.session.commit()
        await self.user_repo.session.refresh(user)

        logger.bind(user_id=str(user.id), phone_code=user.phone_code, mobile=user.mobile).info(
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
            # 0. 行为安全验证码防刷校验
            client_ip = ip_address or "127.0.0.1"
            await verify_captcha_async(login_data.captcha_ticket, login_data.captcha_randstr, client_ip)

            # 1. 查询用户
            user = await self.user_repo.get_by_mobile(login_data.phone_code, login_data.mobile)
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
            if not reason:
                reason = "异常拒绝/CAPTCHA拦截"
            raise e
        finally:
            # 5. 无论成功失败，都持久化记录双轨登录日志
            login_log = LoginLog(
                actor_type="user",
                actor_id=user_id_for_log if user_id_for_log else None,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status,
                reason=reason,
            )
            self.user_repo.session.add(login_log)
            # 因为是在终于边界强制插入，需要利用底层机制或者依赖 Session 自己包裹事务的 commit。
            # FastAPI 依赖里通常是在请求结束时做一层全链路 commit。为了强保成功/失败必须写入，
            # auth log 我们这通常在中间件独立或者通过抛出异常外层控制，但目前由于我们在 Service 中，
            # 我们可以直接执行强制落库：
            try:
                await self.user_repo.session.commit()
            except Exception as commit_e:
                await self.user_repo.session.rollback()
                logger.error(f"Failed to save login log: {commit_e}")

            logger.bind(
                user_id=user_id_for_log if user_id_for_log else "Unknown",
                login_ip=ip_address,
                user_agent=user_agent,
                status=status,
                reason=reason,
            ).info("Login DB attempt recorded")

    async def refresh_token(self, refresh_token: str) -> Token:
        """
        使用 Refresh Token 换取新 Token (会话族谱追踪方案)。
        """
        # 1. 原子 RENAME：尝试将 Token 标记为消费状态
        # 如果 Token 存在，则它成功转移到 consumed_token:* 中，避免了任何并发导致的同时刷新
        try:
            await self.redis.rename(
                f"refresh_token:{refresh_token}", 
                f"consumed_token:{refresh_token}"
            )
            # RENAME 成功，我们赢得了并发锁！当前请求是唯一合法的刷新者。
            # 解析背后的族谱信息 (因为存入 redis 时一定会被 decode 成 str，所以这里收到的是 str)
            val = await self.redis.get(f"consumed_token:{refresh_token}")
            
            if not val:
                raise AppException(SystemErrorCode.UNAUTHORIZED, message="Refresh token 族谱破坏")
                
            # (作为防御性代码) 续期这个被消费标记 Token 的 TTL，用来做后续钓鱼
            await self.redis.expire(f"consumed_token:{refresh_token}", timedelta(days=7))
            
            session_id, user_id = val.split(":")
            
        except ResponseError:
            # RENAME 失败 (通常是因为 key 不存在)
            # 有两种可能：是真的过期了，或者是已经被（黑客/本人的旧设备）用过了被挪到了 consumed 里。
            val = await self.redis.get(f"consumed_token:{refresh_token}")
            
            if val:
                # 💥 钓鱼成功：有人试图使用一张已经消费过的旧车票！这是重放或 Token 泄露！
                session_id, user_id = val.split(":")
                
                # 诛连机制：找到该 session 目前合法的“那颗果子”，直接删除！
                active_token = await self.redis.get(f"session_active:{session_id}")
                if active_token:
                    await self.redis.delete(f"refresh_token:{active_token}")
                
                await self.redis.delete(f"session_active:{session_id}")
                
                # 抛出最高安全级别异常，前端应当强制下线并提示用户修改密码
                raise AppException(AuthError.TOKEN_THEFT_DETECTED)
            else:
                # 连 consumed 里都没有，那就是确实没登录或真过期了
                raise AppException(SystemErrorCode.UNAUTHORIZED, message="Refresh token 无效或已过期")

        # 2. 强制查库校验：确保被软删除或封禁的用户无法继续续签
        user = await self.user_repo.get(user_id)
        
        if not user or user.is_deleted:
            raise AppException(
                SystemErrorCode.UNAUTHORIZED, message="用户不存在或已被注销"
            )
            
        if not user.is_active:
            raise AppException(
                SystemErrorCode.UNAUTHORIZED, message="用户已被禁用/封禁"
            )

        # 3. 带着继承的族谱 session_id，签发新 Token 替代，树重新生效
        return await self._create_tokens(user_id=user_id, session_id=session_id)

    async def logout(self, refresh_token: str) -> None:
        """
        用户登出。
        提取族谱，将当前令牌和活跃标记一并抹除。
        """
        val = await self.redis.get(f"refresh_token:{refresh_token}")
        if val:
            session_id, _ = val.split(":")
            await self.redis.delete(f"session_active:{session_id}")
            
        await self.redis.delete(f"refresh_token:{refresh_token}")

    async def _create_tokens(self, user_id: str, session_id: str | None = None) -> Token:
        """
        [内部方法] 构造 Token 响应并持久化 Refresh Token 及会话族谱。
        """
        if not session_id:
            # 首次登录/注册，生成新的会话族谱 ID
            session_id = str(uuid7())

        # 1. 生成 Access Token (JWT)
        access_token = create_access_token(subject=user_id)

        # 2. 生成 Refresh Token (高熵随机串)
        # 用作当前 session_active 的有效凭证
        refresh_token = secrets.token_urlsafe(32)
        ttl = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        # 3. 存入 Redis 会话族谱
        # Key 1: refresh_token:X -> "session_id:user_id"
        await self.redis.setex(
            f"refresh_token:{refresh_token}",
            ttl,
            f"{session_id}:{user_id}",
        )

        # Key 2: session_active:SessionID -> "X" (锚定当前树唯一的存活果子)
        await self.redis.setex(
            f"session_active:{session_id}",
            ttl,
            refresh_token,
        )

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            token_type="bearer",
        )
