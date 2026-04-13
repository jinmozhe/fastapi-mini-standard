"""
File: app/domains/auth/service.py
Description: 认证领域服务 (Service)

本模块封装认证核心业务逻辑：
1. 密码登录: 验证手机号与密码，签发双 Token。
2. 短信验证码登录: 验证码校验 → 查手机号 → 不存在则自动注册 → 签发 Token。
3. 微信小程序登录: code2session → 解密手机号 → 合流用户 → 签发 Token。
4. 刷新令牌: 验证 Redis 中的 Refresh Token，执行旋转策略 (Rotation)。
5. 用户登出: 销毁 Refresh Token。

Author: jinmozhe
Created: 2025-12-05
Updated: 2026-04-12 (v3.0: 多渠道认证体系)
"""

import secrets
import uuid as uuid_mod
from datetime import timedelta

from redis.asyncio import Redis
from redis.exceptions import ResponseError
from uuid6 import uuid7

from app.core.config import settings
from app.core.error_code import SystemErrorCode
from app.core.exceptions import AppException
from app.core.logging import logger
from app.core.captcha import verify_captcha_async
from app.core.sms import verify_sms_code
from app.core.wechat import code2session, decrypt_phone_number
from app.db.models.log import LoginLog
from app.db.models.user import User
from app.db.models.user_social import UserSocial
from app.core.security import (
    create_access_token,
    get_password_hash_async,
    verify_password_async,
)
from app.domains.auth.constants import AuthError
from app.core.error_code import SystemErrorCode
from app.domains.auth.repository import UserSocialRepository
from app.domains.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    SmsLoginRequest,
    Token,
    WechatCompleteRequest,
    WechatLoginRequest,
    WechatScanResponse,
)
from app.domains.users.repository import UserRepository


class AuthService:
    """
    认证服务类。

    支持三种登录渠道：
    - 手机号 + 密码（传统登录）
    - 手机号 + 短信验证码（注册即登录）
    - 微信小程序授权（注册即登录 + 社交绑定）
    """

    def __init__(
        self,
        user_repo: UserRepository,
        redis: Redis,
        social_repo: UserSocialRepository | None = None,
    ):
        self.user_repo = user_repo
        self.redis = redis
        self.social_repo = social_repo

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

        # 5. 如果携带邀请码，绑定推荐关系
        if reg_data.invite_code:
            try:
                from app.domains.referrals.service import ReferralService
                referral_svc = ReferralService(self.user_repo.session)
                await referral_svc.bind_inviter(user.id, reg_data.invite_code)
            except Exception as e:
                # 邀请码绑定失败不影响注册流程，仅记录日志
                logger.warning(
                    "invite_code_bind_failed",
                    user_id=str(user.id),
                    invite_code=reg_data.invite_code,
                    error=str(e),
                )

        await self.user_repo.session.commit()
        await self.user_repo.session.refresh(user)

        logger.bind(user_id=str(user.id), phone_code=user.phone_code, mobile=user.mobile).info(
            "User registered successfully"
        )

        # 6. 自动生成 Token (注册后自动登录)
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

            # 2. 检查用户是否设置了密码（小程序/SMS 注册的用户可能没有密码）
            if not user.hashed_password:
                reason = "尚未设置密码"
                raise AppException(AuthError.PASSWORD_NOT_SET)

            # 3. 校验密码
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

    # ==========================================================================
    # 短信验证码登录 (注册即登录)
    # ==========================================================================

    async def sms_login(
        self,
        data: SmsLoginRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Token:
        """
        短信验证码登录（注册即登录）。

        流程：
        1. 验证短信验证码 (从 Redis 比对并销毁)
        2. 查库: 手机号是否已存在
        3. 不存在 → 自动创建 User (hashed_password=None)
        4. 如果有 inviter_id → 绑定推荐关系
        5. 签发双 Token
        """
        # 1. 验证短信验证码
        await verify_sms_code(self.redis, data.phone_code, data.mobile, data.code)

        # 2. 查库 (get_by_mobile 自动过滤 is_deleted=True)
        user = await self.user_repo.get_by_mobile(data.phone_code, data.mobile)
        is_new = False

        if not user:
            # 安全兜底：检查是否有已注销的同手机号用户
            from sqlalchemy import select
            deleted_check = select(User).where(
                User.phone_code == data.phone_code,
                User.mobile == data.mobile,
                User.is_deleted.is_(True),
            )
            deleted_result = await self.user_repo.session.execute(deleted_check)
            if deleted_result.scalar_one_or_none():
                raise AppException(AuthError.ACCOUNT_DELETED)

            # 3. 自动注册 (无密码用户)
            user = User(
                phone_code=data.phone_code,
                mobile=data.mobile,
                hashed_password=None,
            )
            self.user_repo.session.add(user)
            await self.user_repo.session.flush()
            is_new = True

            logger.bind(
                user_id=str(user.id), mobile=data.mobile
            ).info("用户通过短信验证码自动注册")

        # 检查用户状态
        if not user.is_active:
            raise AppException(AuthError.ACCOUNT_LOCKED)

        # 4. 绑定推荐关系 (仅新注册用户)
        if is_new and data.inviter_id:
            await self._bind_inviter(user.id, data.inviter_id)

        # 5. 记录登录日志
        login_log = LoginLog(
            actor_type="user",
            actor_id=str(user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            status=True,
            reason="短信验证码登录成功",
        )
        self.user_repo.session.add(login_log)
        await self.user_repo.session.commit()

        # 6. 签发 Token
        return await self._create_tokens(user_id=str(user.id))

    # ==========================================================================
    # 微信小程序授权登录
    # ==========================================================================

    async def wechat_login(
        self,
        data: WechatLoginRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Token:
        """
        微信小程序授权登录（注册即登录 + 社交绑定）。

        流程：
        1. 调用微信 code2session → 获取 openid + session_key
        2. 解密手机号
        3. 查 user_socials: 是否已有绑定？
           - 有 → 更新 session_key，直接签发
           - 没有 → 用手机号查 users 做合流或新建
        4. 签发双 Token
        """
        assert self.social_repo is not None, "wechat_login 需要 social_repo"

        # 1. 获取 openid + session_key
        wechat_session = await code2session(data.js_code)

        # 2. 解密手机号
        phone_info = decrypt_phone_number(
            wechat_session.session_key, data.encrypted_data, data.iv
        )
        phone_code = f"+{phone_info.country_code}"
        mobile = phone_info.pure_phone_number

        # 3. 查绑定记录
        social = await self.social_repo.get_by_platform_openid(
            platform="wechat_mini", openid=wechat_session.openid
        )

        if social:
            # 已有绑定 → 更新 session_key → 直接签发
            await self.social_repo.update_session_key(
                social, wechat_session.session_key
            )
            user = await self.user_repo.get(str(social.user_id))
            if not user or user.is_deleted or not user.is_active:
                raise AppException(AuthError.ACCOUNT_LOCKED)
            await self.user_repo.session.commit()
            return await self._create_tokens(user_id=str(user.id))

        # 没有绑定 → 用手机号做合流
        user = await self.user_repo.get_by_mobile(phone_code, mobile)
        is_new = False

        if not user:
            # 新建用户 (无密码)
            user = User(
                phone_code=phone_code,
                mobile=mobile,
                hashed_password=None,
            )
            self.user_repo.session.add(user)
            await self.user_repo.session.flush()
            is_new = True

            logger.bind(
                user_id=str(user.id), mobile=mobile
            ).info("用户通过微信小程序自动注册")

        if not user.is_active:
            raise AppException(AuthError.ACCOUNT_LOCKED)

        # 创建 UserSocial 绑定
        new_social = UserSocial(
            user_id=user.id,
            platform="wechat_mini",
            openid=wechat_session.openid,
            unionid=wechat_session.unionid,
            session_key=wechat_session.session_key,
        )
        await self.social_repo.create_binding(new_social)

        # 绑定推荐关系 (仅新注册用户)
        if is_new and data.inviter_id:
            await self._bind_inviter(user.id, data.inviter_id)

        # 记录登录日志
        login_log = LoginLog(
            actor_type="user",
            actor_id=str(user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            status=True,
            reason="微信小程序登录成功",
        )
        self.user_repo.session.add(login_log)
        await self.user_repo.session.commit()

        return await self._create_tokens(user_id=str(user.id))

    # ==========================================================================
    # 推荐关系绑定 (内部方法)
    # ==========================================================================

    async def _bind_inviter(
        self, user_id: uuid_mod.UUID, inviter_id_str: str
    ) -> None:
        """
        为新注册用户绑定推荐关系。

        在 user_level_profiles 中设置 inviter_id，并累加推荐人的邀请计数。
        如果推荐人不存在或 ID 无效，静默跳过（不影响注册主流程）。
        """
        from app.db.models.user_level import UserLevelProfile
        from sqlalchemy import select, update

        try:
            inviter_uuid = uuid_mod.UUID(inviter_id_str)

            # 校验推荐人存在
            inviter = await self.user_repo.get(inviter_id_str)
            if not inviter:
                logger.warning(f"推荐人 {inviter_id_str} 不存在，跳过绑定")
                return

            # 查找或创建当前用户的 level_profile
            stmt = select(UserLevelProfile).where(
                UserLevelProfile.user_id == user_id
            )
            result = await self.user_repo.session.execute(stmt)
            profile = result.scalar_one_or_none()

            if not profile:
                profile = UserLevelProfile(
                    user_id=user_id,
                    inviter_id=inviter_uuid,
                )
                self.user_repo.session.add(profile)
            else:
                profile.inviter_id = inviter_uuid

            # 推荐人邀请计数 +1
            inviter_stmt = select(UserLevelProfile).where(
                UserLevelProfile.user_id == inviter_uuid
            )
            inviter_result = await self.user_repo.session.execute(inviter_stmt)
            inviter_profile = inviter_result.scalar_one_or_none()

            if inviter_profile:
                inviter_profile.total_invite_number += 1
            else:
                inviter_profile = UserLevelProfile(
                    user_id=inviter_uuid,
                    total_invite_number=1,
                )
                self.user_repo.session.add(inviter_profile)

            await self.user_repo.session.flush()
            logger.info(
                f"推荐关系绑定成功: {user_id} ← inviter: {inviter_id_str}"
            )

        except (ValueError, Exception) as e:
            logger.warning(f"推荐关系绑定失败 (不影响注册): {e}")

    # ==========================================================================
    # 已登录用户绑定微信
    # ==========================================================================

    # platform 白名单
    ALLOWED_PLATFORMS = {"wechat_mini", "wechat_mp", "wechat_web"}

    async def bind_wechat(
        self,
        user_id: uuid_mod.UUID,
        code: str,
        platform: str = "wechat_mini",
    ) -> None:
        """
        已登录用户绑定微信。

        流程：
        1. 校验 platform 白名单
        2. 根据 platform 选择调用小程序 code2session 或开放平台 code2access_token
        3. 检查该 openid 是否已被别人绑定
        4. 创建 UserSocial 绑定记录
        """
        assert self.social_repo is not None

        # 1. platform 白名单校验
        if platform not in self.ALLOWED_PLATFORMS:
            raise AppException(
                SystemErrorCode.BAD_REQUEST,
                message=f"不支持的平台类型: {platform}",
            )

        # 2. 根据平台获取 openid
        if platform == "wechat_mini":
            session_result = await code2session(code)
            openid = session_result.openid
            unionid = session_result.unionid
            session_key = session_result.session_key
        else:
            from app.core.wechat import code2access_token
            oauth_result = await code2access_token(code)
            openid = oauth_result.openid
            unionid = oauth_result.unionid
            session_key = None

        # 3. 检查是否已被绑定
        existing = await self.social_repo.get_by_platform_openid(platform, openid)
        if existing:
            if existing.user_id == user_id:
                return  # 已绑定到自己，静默成功
            raise AppException(AuthError.WECHAT_ALREADY_BOUND)

        # 4. 创建绑定
        social = UserSocial(
            user_id=user_id,
            platform=platform,
            openid=openid,
            unionid=unionid,
            session_key=session_key,
        )
        await self.social_repo.create_binding(social)
        await self.user_repo.session.commit()

    # ==========================================================================
    # 已登录用户解绑微信
    # ==========================================================================

    async def unbind_wechat(
        self,
        user_id: uuid_mod.UUID,
        platform: str = "wechat_mini",
    ) -> None:
        """
        解绑微信。删除当前用户在指定平台的绑定记录。

        安全检查：确保用户至少保留一种登录方式（密码或其他社交绑定），
        否则解绑后将无法登录。
        """
        assert self.social_repo is not None
        from sqlalchemy import select, func

        # 查找要解绑的记录
        stmt = select(UserSocial).where(
            UserSocial.user_id == user_id,
            UserSocial.platform == platform,
        )
        result = await self.user_repo.session.execute(stmt)
        social = result.scalar_one_or_none()

        if not social:
            raise AppException(AuthError.WECHAT_NOT_BOUND)

        # 安全检查：解绑后用户是否还有其他登录方式？
        user = await self.user_repo.get(str(user_id))
        has_password = user and user.hashed_password

        # 统计该用户的其他社交绑定数量
        count_stmt = select(func.count()).select_from(UserSocial).where(
            UserSocial.user_id == user_id,
            UserSocial.platform != platform,
        )
        count_result = await self.user_repo.session.execute(count_stmt)
        other_bindings = count_result.scalar_one()

        if not has_password and other_bindings == 0:
            raise AppException(
                AuthError.UNBIND_LAST_METHOD,
            )

        await self.user_repo.session.delete(social)
        await self.user_repo.session.commit()

    # ==========================================================================
    # 网页端微信扫码登录
    # ==========================================================================

    async def wechat_scan_login(self, code: str) -> WechatScanResponse:
        """
        网页端微信扫码登录。

        流程：
        1. 用 code 换取 openid
        2. 查 user_socials: 是否已有绑定？
           - 有 → 老用户，直接签发正式 Token
           - 没有 → 新用户，生成临时凭证，要求绑定手机号
        """
        assert self.social_repo is not None
        from app.core.wechat import code2access_token

        # 1. 获取 openid
        oauth_result = await code2access_token(code)

        # 2. 查绑定
        social = await self.social_repo.get_by_platform_openid(
            "wechat_web", oauth_result.openid
        )

        if social:
            # 老用户 → 直接登录
            user = await self.user_repo.get(str(social.user_id))
            if not user or user.is_deleted or not user.is_active:
                raise AppException(AuthError.ACCOUNT_LOCKED)

            token = await self._create_tokens(user_id=str(user.id))
            return WechatScanResponse(
                is_new=False,
                token=token,
                nickname=social.nickname,
                avatar=social.avatar,
            )

        # 新用户 → 生成临时凭证，存入 Redis (5 分钟 TTL)
        import secrets
        temp_token = secrets.token_urlsafe(32)
        import json
        temp_data = json.dumps({
            "openid": oauth_result.openid,
            "unionid": oauth_result.unionid,
            "nickname": oauth_result.nickname,
            "avatar": oauth_result.avatar,
            "platform": "wechat_web",
        })
        await self.redis.setex(
            f"wechat_temp:{temp_token}", 300, temp_data
        )

        return WechatScanResponse(
            is_new=True,
            temp_token=temp_token,
            nickname=oauth_result.nickname,
            avatar=oauth_result.avatar,
        )

    # ==========================================================================
    # 扫码登录 → 完成注册 (绑定手机号)
    # ==========================================================================

    async def wechat_complete_registration(
        self,
        data: WechatCompleteRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Token:
        """
        扫码登录后绑定手机号完成注册。

        流程：
        1. 从 Redis 取出临时凭证数据 (openid/unionid 等)
        2. 验证短信验证码
        3. 用手机号查库做合流或新建
        4. 创建 UserSocial 绑定
        5. 签发正式 Token
        """
        assert self.social_repo is not None

        # 1. 取临时凭证
        import json
        temp_data_raw = await self.redis.get(f"wechat_temp:{data.temp_token}")
        if not temp_data_raw:
            raise AppException(AuthError.TEMP_TOKEN_INVALID)

        temp_str = temp_data_raw if isinstance(temp_data_raw, str) else temp_data_raw.decode()
        temp_info = json.loads(temp_str)

        # 立即销毁临时凭证 (一次性)
        await self.redis.delete(f"wechat_temp:{data.temp_token}")

        # 2. 验证短信验证码
        await verify_sms_code(self.redis, data.phone_code, data.mobile, data.code)

        # 3. 用手机号做合流 (get_by_mobile 自动过滤 is_deleted)
        user = await self.user_repo.get_by_mobile(data.phone_code, data.mobile)
        is_new = False

        if not user:
            # 安全兜底：检查是否有已注销的同手机号用户
            from sqlalchemy import select as sa_select
            deleted_check = sa_select(User).where(
                User.phone_code == data.phone_code,
                User.mobile == data.mobile,
                User.is_deleted.is_(True),
            )
            deleted_result = await self.user_repo.session.execute(deleted_check)
            if deleted_result.scalar_one_or_none():
                raise AppException(AuthError.ACCOUNT_DELETED)

            user = User(
                phone_code=data.phone_code,
                mobile=data.mobile,
                hashed_password=None,
                nickname=temp_info.get("nickname"),
                avatar=temp_info.get("avatar"),
            )
            self.user_repo.session.add(user)
            await self.user_repo.session.flush()
            is_new = True
            logger.bind(user_id=str(user.id)).info("用户通过微信扫码+手机号完成注册")

        if not user.is_active:
            raise AppException(AuthError.ACCOUNT_LOCKED)

        # 4. 创建社交绑定
        social = UserSocial(
            user_id=user.id,
            platform=temp_info.get("platform", "wechat_web"),
            openid=temp_info["openid"],
            unionid=temp_info.get("unionid"),
            nickname=temp_info.get("nickname"),
            avatar=temp_info.get("avatar"),
        )
        await self.social_repo.create_binding(social)

        # 推荐关系
        if is_new and data.inviter_id:
            await self._bind_inviter(user.id, data.inviter_id)

        # 登录日志
        login_log = LoginLog(
            actor_type="user",
            actor_id=str(user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            status=True,
            reason="微信扫码+手机号注册成功",
        )
        self.user_repo.session.add(login_log)
        await self.user_repo.session.commit()

        return await self._create_tokens(user_id=str(user.id))

    # ==========================================================================
    # 设置/修改密码
    # ==========================================================================

    async def set_password(
        self,
        user_id: uuid_mod.UUID,
        new_password: str,
        old_password: str | None = None,
    ) -> None:
        """
        设置或修改密码。

        场景：
        - 无密码用户首次设置密码：old_password 为空即可
        - 已有密码用户修改密码：必须验证 old_password

        Args:
            user_id: 当前登录用户 ID
            new_password: 新密码
            old_password: 旧密码（已有密码时必传）
        """
        user = await self.user_repo.get(str(user_id))
        if not user:
            raise AppException(SystemErrorCode.UNAUTHORIZED)

        # 如果已有密码，必须验证旧密码
        if user.hashed_password:
            if not old_password:
                raise AppException(
                    AuthError.INVALID_CREDENTIALS,
                    message="修改密码需要提供旧密码",
                )
            if not await verify_password_async(old_password, user.hashed_password):
                raise AppException(
                    AuthError.INVALID_CREDENTIALS,
                    message="旧密码错误",
                )

        # 哈希新密码并保存
        user.hashed_password = await get_password_hash_async(new_password)
        await self.user_repo.session.commit()
        logger.bind(user_id=str(user_id)).info("用户密码已更新")

    # ==========================================================================
    # Token 刷新 (Rotation 策略)
    # ==========================================================================

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
