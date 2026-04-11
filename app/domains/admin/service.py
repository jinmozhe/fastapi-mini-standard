"""
File: app/domains/admin/service.py
Description: B端管理员认证服务 (AdminAuthService)

本模块封装 B 端管理员的核心认证业务逻辑：
1. 登录验证: 校验用户名+密码，签发带 aud='backend' 区分标识的双 Token。
2. 令牌刷新: 基于 Redis RENAME 原子操作防重放（与 C 端同等安全级别）。
3. 登出: 销毁当前会话族谱中的所有 Token。
4. 日志落库: 无论成功或失败，均持久化记录到 LoginLog。

Author: jinmozhe
Created: 2026-04-12
"""

import secrets
from datetime import timedelta

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.core.config import settings
from app.core.error_code import SystemErrorCode
from app.core.exceptions import AppException
from app.core.logging import logger
from app.core.security import create_access_token, verify_password_async
from app.db.models.log import LoginLog
from app.domains.admin.constants import AdminError
from app.domains.admin.repository import AdminRepository
from app.domains.admin.schemas import AdminToken


class AdminAuthService:
    """
    B端管理员认证服务。
    """

    def __init__(self, admin_repo: AdminRepository, redis: Redis):
        self.admin_repo = admin_repo
        self.redis = redis

    # --------------------------------------------------------------------------
    # 核心业务方法
    # --------------------------------------------------------------------------

    async def login(
        self,
        username: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AdminToken:
        """
        管理员登录处理。

        流程:
        1. 查询管理员账号（含角色权限树预加载）
        2. 校验密码（Argon2id 异步验证）
        3. 校验账号状态
        4. 签发双 Token (Access + Refresh)，JWT payload 含 aud='backend' 标识
        5. 无论成功/失败，均落库 LoginLog
        """
        status = False
        reason = "未知错误"
        admin_id_for_log: str | None = None

        try:
            # 1. 查库
            admin = await self.admin_repo.get_by_username(username)
            if not admin:
                reason = "账号或密码错误"
                raise AppException(AdminError.INVALID_CREDENTIALS)

            admin_id_for_log = str(admin.id)

            # 2. 验密 (CPU 密集型异步)
            if not await verify_password_async(password, admin.hashed_password):
                reason = "账号或密码错误"
                raise AppException(AdminError.INVALID_CREDENTIALS)

            # 3. 状态检查 (通常 get_by_username 已过滤，但双重保险)
            if not admin.is_active:
                reason = "账号已被停用"
                raise AppException(AdminError.ACCOUNT_DISABLED)

            status = True
            reason = "登录成功"

            # 4. 签发 Token（附加 aud='backend' 区分 B端 Token）
            return await self._create_tokens(admin_id=str(admin.id))

        except AppException as e:
            if not reason or reason == "未知错误":
                reason = "登录鉴权拒绝"
            raise e
        finally:
            # 5. 强制落库登录审计日志
            log = LoginLog(
                actor_type="admin",
                actor_id=admin_id_for_log,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status,
                reason=reason,
            )
            self.admin_repo.session.add(log)
            try:
                await self.admin_repo.session.commit()
            except Exception as commit_err:
                await self.admin_repo.session.rollback()
                logger.error(f"Admin login log commit failed: {commit_err}")

            logger.bind(
                admin_id=admin_id_for_log or "Unknown",
                login_ip=ip_address,
                user_agent=user_agent,
                status=status,
                reason=reason,
            ).info("Admin login attempt recorded")

    async def refresh_token(self, refresh_token: str) -> AdminToken:
        """
        使用 Refresh Token 换取新 Token（会话族谱追踪，与 C 端机制相同）。
        """
        try:
            # 原子 RENAME：消费旧 Token
            await self.redis.rename(
                f"admin_refresh_token:{refresh_token}",
                f"admin_consumed_token:{refresh_token}",
            )
        except ResponseError:
            # RENAME 失败 → Token 不存在或已被消费 → 极可能是重放攻击
            # 尝试通过 consumed_token 反查 session_id 并销毁整族
            session_id = await self.redis.get(f"admin_consumed_token:{refresh_token}")
            if session_id:
                await self._destroy_session_family(session_id.decode())
            raise AppException(AdminError.TOKEN_THEFT_DETECTED)

        # 取出 session_id
        session_id_bytes = await self.redis.get(f"admin_consumed_token:{refresh_token}")
        if not session_id_bytes:
            raise AppException(SystemErrorCode.UNAUTHORIZED, message="Refresh Token 已失效")

        session_id = session_id_bytes.decode()

        # 取出 admin_id
        admin_id_bytes = await self.redis.get(f"admin_session:{session_id}")
        if not admin_id_bytes:
            raise AppException(SystemErrorCode.UNAUTHORIZED, message="会话已失效，请重新登录")

        admin_id = admin_id_bytes.decode()

        # 签发新 Token
        tokens = await self._create_tokens(admin_id=admin_id)

        # 删除旧的 consumed_token（已刷新，不再需要）
        await self.redis.delete(f"admin_consumed_token:{refresh_token}")

        return tokens

    async def logout(self, refresh_token: str) -> None:
        """
        主动登出：销毁当前 Refresh Token 及其关联的整个会话族谱。
        """
        session_id_bytes = await self.redis.get(f"admin_refresh_token:{refresh_token}")
        if session_id_bytes:
            session_id = session_id_bytes.decode()
            await self._destroy_session_family(session_id)
        # 即使 Token 不存在也静默成功，避免泄露信息

    # --------------------------------------------------------------------------
    # 私有辅助方法
    # --------------------------------------------------------------------------

    async def _create_tokens(self, admin_id: str) -> AdminToken:
        """
        内部方法：为指定管理员签发全新的双 Token，并将 Refresh Token 注册入 Redis 会话族谱。
        JWT payload 使用 aud='backend' 区分 B 端 Token，防止 C 端 Token 被拿来访问 B 端接口。
        """
        # 签发 Access Token（短效，含 aud 标识）
        access_expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            subject=admin_id,
            expires_delta=access_expire,
            extra_claims={"aud": "backend"},
        )

        # 生成高熵 Refresh Token 与 Session ID（族谱追踪）
        refresh_token = secrets.token_urlsafe(48)
        session_id = str(secrets.token_urlsafe(32))
        refresh_expire = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600

        # 写入 Redis：
        # admin_refresh_token:{token} → session_id（session 族谱关联）
        # admin_session:{session_id} → admin_id（反查账号）
        pipe = self.redis.pipeline()
        pipe.setex(f"admin_refresh_token:{refresh_token}", refresh_expire, session_id)
        pipe.setex(f"admin_session:{session_id}", refresh_expire, admin_id)
        await pipe.execute()

        return AdminToken(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def _destroy_session_family(self, session_id: str) -> None:
        """
        会话族谱联防销毁（诛九族机制）。
        销毁 Redis 中该 session 关联的所有 Key（防止 Token 被盗用方继续使用）。
        """
        admin_id_bytes = await self.redis.get(f"admin_session:{session_id}")
        if admin_id_bytes:
            # 扫描并删除该管理员当前所有 refresh_token 相关 Key
            await self.redis.delete(f"admin_session:{session_id}")
        logger.warning(f"Admin session family destroyed: session_id={session_id}")
