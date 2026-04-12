"""
File: app/domains/auth/repository.py
Description: 认证领域仓储层 (UserSocial + SmsLog)

新增两个 Repository 用于社交登录绑定和短信审计日志。

Author: jinmozhe
Created: 2026-04-12
"""

from sqlalchemy import select

from app.db.models.sms_log import SmsLog
from app.db.models.user_social import UserSocial
from app.db.repositories.base import BaseRepository


class UserSocialRepository(BaseRepository[UserSocial, None, None]):
    """
    用户三方绑定仓储

    核心查询：
    - get_by_platform_openid: 根据平台+openid 查找绑定记录
    """

    async def get_by_platform_openid(
        self, platform: str, openid: str
    ) -> UserSocial | None:
        """根据平台标识和 openid 查找绑定记录"""
        stmt = select(UserSocial).where(
            UserSocial.platform == platform,
            UserSocial.openid == openid,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_binding(self, social: UserSocial) -> UserSocial:
        """创建三方绑定记录"""
        self.session.add(social)
        await self.session.flush()
        return social

    async def update_session_key(
        self, social: UserSocial, session_key: str
    ) -> None:
        """更新微信 session_key（每次 code2session 后刷新）"""
        social.session_key = session_key


class SmsLogRepository:
    """
    短信发送日志仓储

    只写仓储：短信日志只做插入，不做修改和删除。
    """

    def __init__(self, session):
        self.session = session

    async def create(self, log: SmsLog) -> SmsLog:
        """写入一条短信发送记录"""
        self.session.add(log)
        await self.session.flush()
        return log
