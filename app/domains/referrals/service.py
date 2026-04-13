"""
File: app/domains/referrals/service.py
Description: 推荐关系核心业务逻辑

核心方法：
- get_or_create_invite_code()  → 获取/生成邀请码
- bind_inviter()               → 注册时绑定推荐人
- get_inviter_info()           → 查看我的推荐人
- get_team_members()           → 查看团队成员（1/2/3 级）
- get_team_stats()             → 团队统计
- admin_bind()                 → 管理员手动绑定
- admin_unbind()               → 管理员解绑

Author: jinmozhe
Created: 2026-04-13
"""

import random
import string
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.logging import logger
from app.db.models.user_level import UserLevelProfile
from app.domains.referrals.constants import INVITE_CODE_LENGTH, ReferralError
from app.domains.referrals.repository import ReferralRepository
from app.domains.referrals.schemas import (
    InviteCodeResult,
    InviterInfo,
    TeamMemberItem,
    TeamStats,
)


class ReferralService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ReferralRepository(db)

    # --------------------------------------------------------------------------
    # 邀请码生成
    # --------------------------------------------------------------------------
    @staticmethod
    def _generate_invite_code() -> str:
        """生成 6 位大写字母+数字混合邀请码"""
        chars = string.ascii_uppercase + string.digits
        return "".join(random.choices(chars, k=INVITE_CODE_LENGTH))

    # --------------------------------------------------------------------------
    # 1. 获取/生成我的邀请码
    # --------------------------------------------------------------------------
    async def get_or_create_invite_code(self, user_id: UUID) -> InviteCodeResult:
        """
        懒生成邀请码：首次请求时自动生成并持久化。
        后续请求直接返回。
        """
        profile = await self.repo.get_profile_by_user(user_id)
        if not profile:
            # 如果 Profile 不存在，创建一个
            profile = UserLevelProfile(user_id=user_id)
            self.db.add(profile)
            await self.db.flush()

        if not profile.invite_code:
            # 生成唯一邀请码（重试 5 次防冲突）
            for _ in range(5):
                code = self._generate_invite_code()
                existing = await self.repo.get_profile_by_invite_code(code)
                if not existing:
                    profile.invite_code = code
                    break
            else:
                # 5 次都冲突（概率极低），用长码兜底
                profile.invite_code = self._generate_invite_code() + self._generate_invite_code()

        return InviteCodeResult(
            invite_code=profile.invite_code,
            user_id=user_id,
        )

    # --------------------------------------------------------------------------
    # 2. 注册时绑定推荐人（由 AuthService 调用）
    # --------------------------------------------------------------------------
    async def bind_inviter(self, user_id: UUID, invite_code: str) -> None:
        """
        通过邀请码绑定推荐人。

        校验规则：
        1. 邀请码有效
        2. 不能自己邀请自己
        3. 不能反向绑定（防循环）
        4. 用户未绑定过推荐人
        """
        # 查邀请码对应的推荐人
        inviter_profile = await self.repo.get_profile_by_invite_code(invite_code)
        if not inviter_profile:
            raise AppException(ReferralError.INVITE_CODE_INVALID)

        inviter_id = inviter_profile.user_id

        # 不能自己邀请自己
        if inviter_id == user_id:
            raise AppException(ReferralError.SELF_INVITE)

        # 获取当前用户的 Profile
        profile = await self.repo.get_profile_by_user(user_id)
        if not profile:
            profile = UserLevelProfile(user_id=user_id)
            self.db.add(profile)
            await self.db.flush()

        if profile.inviter_id:
            raise AppException(ReferralError.ALREADY_BOUND)

        # 防循环：检查 inviter 的上级链中是否包含 user_id
        is_circular = await self.repo.is_in_chain(inviter_id, user_id)
        if is_circular:
            raise AppException(ReferralError.CIRCULAR_BIND)

        # 绑定
        now_iso = datetime.now(timezone.utc).isoformat()
        profile.inviter_id = inviter_id
        profile.invited_at = now_iso

        # 更新推荐人的邀请计数
        inviter_profile.total_invite_number += 1

        logger.info(
            "referral_bound",
            user_id=str(user_id),
            inviter_id=str(inviter_id),
            invite_code=invite_code,
        )

    # --------------------------------------------------------------------------
    # 3. 查看我的推荐人
    # --------------------------------------------------------------------------
    async def get_inviter_info(self, user_id: UUID) -> InviterInfo | None:
        """查看谁邀请了我"""
        profile = await self.repo.get_profile_by_user(user_id)
        if not profile or not profile.inviter_id:
            return None

        inviter = await self.repo.get_user(profile.inviter_id)
        if not inviter:
            return None

        return InviterInfo(
            user_id=inviter.id,
            nickname=inviter.nickname,
            avatar=inviter.avatar,
            invited_at=profile.invited_at,
        )

    # --------------------------------------------------------------------------
    # 4. 查看团队成员（按级别）
    # --------------------------------------------------------------------------
    async def get_team_members(
        self,
        user_id: UUID,
        level: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TeamMemberItem], int]:
        """
        查看团队成员。
        level: 1=一级（直接邀请），2=二级，3=三级
        """
        if level == 1:
            rows, total = await self.repo.get_direct_invitees(user_id, page, page_size)
        elif level == 2:
            # 二级：先查一级的 IDs，再查这些人的直接下级
            first_ids = await self.repo.get_all_direct_invitee_ids(user_id)
            if not first_ids:
                return [], 0
            rows, total = await self._get_multi_level_invitees(first_ids, page, page_size)
        elif level == 3:
            # 三级：先查一级 → 二级 IDs → 再查三级
            first_ids = await self.repo.get_all_direct_invitee_ids(user_id)
            if not first_ids:
                return [], 0
            second_ids: list[UUID] = []
            for fid in first_ids:
                second_ids.extend(await self.repo.get_all_direct_invitee_ids(fid))
            if not second_ids:
                return [], 0
            rows, total = await self._get_multi_level_invitees(second_ids, page, page_size)
        else:
            return [], 0

        items = [TeamMemberItem(**r) for r in rows]
        return items, total

    async def _get_multi_level_invitees(
        self,
        parent_ids: list[UUID],
        page: int,
        page_size: int,
    ) -> tuple[list[dict], int]:
        """查询多个父级用户的直接下级（合并分页）"""
        from sqlalchemy import select, func
        from app.db.models.user import User
        from app.db.models.user_level import UserLevel

        conditions = [UserLevelProfile.inviter_id.in_(parent_ids)]

        count_stmt = select(func.count()).select_from(UserLevelProfile).where(*conditions)
        total: int = await self.db.scalar(count_stmt) or 0

        stmt = (
            select(
                UserLevelProfile.user_id,
                UserLevelProfile.total_consume,
                UserLevelProfile.invited_at,
                User.nickname,
                User.avatar,
                User.mobile,
                User.created_at,
                UserLevel.name.label("level_name"),
            )
            .join(User, User.id == UserLevelProfile.user_id)
            .outerjoin(UserLevel, UserLevel.id == UserLevelProfile.level_id)
            .where(*conditions)
            .order_by(UserLevelProfile.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self.db.execute(stmt)
        rows = [dict(row._mapping) for row in result.all()]
        return rows, total

    # --------------------------------------------------------------------------
    # 5. 团队统计
    # --------------------------------------------------------------------------
    async def get_team_stats(self, user_id: UUID) -> TeamStats:
        """团队三级统计"""
        # 一级
        first_ids = await self.repo.get_all_direct_invitee_ids(user_id)
        first_count, first_consume = await self.repo.get_team_stats_for_level(first_ids)

        # 二级
        second_ids: list[UUID] = []
        for fid in first_ids:
            second_ids.extend(await self.repo.get_all_direct_invitee_ids(fid))
        second_count, second_consume = await self.repo.get_team_stats_for_level(second_ids)

        # 三级
        third_ids: list[UUID] = []
        for sid in second_ids:
            third_ids.extend(await self.repo.get_all_direct_invitee_ids(sid))
        third_count, third_consume = await self.repo.get_team_stats_for_level(third_ids)

        return TeamStats(
            first_level_count=first_count,
            second_level_count=second_count,
            third_level_count=third_count,
            total_count=first_count + second_count + third_count,
            first_level_consume=first_consume,
            second_level_consume=second_consume,
            third_level_consume=third_consume,
        )

    # --------------------------------------------------------------------------
    # 6. 管理员手动绑定推荐人
    # --------------------------------------------------------------------------
    async def admin_bind(self, user_id: UUID, inviter_id: UUID) -> None:
        """管理员手动绑定推荐关系"""
        if user_id == inviter_id:
            raise AppException(ReferralError.SELF_INVITE)

        # 验证两个用户都存在
        user = await self.repo.get_user(user_id)
        if not user:
            raise AppException(ReferralError.USER_NOT_FOUND)

        inviter = await self.repo.get_user(inviter_id)
        if not inviter:
            raise AppException(ReferralError.USER_NOT_FOUND, message="推荐人不存在")

        profile = await self.repo.get_profile_by_user(user_id)
        if not profile:
            profile = UserLevelProfile(user_id=user_id)
            self.db.add(profile)
            await self.db.flush()

        if profile.inviter_id:
            raise AppException(ReferralError.ALREADY_BOUND)

        # 防循环
        is_circular = await self.repo.is_in_chain(inviter_id, user_id)
        if is_circular:
            raise AppException(ReferralError.CIRCULAR_BIND)

        now_iso = datetime.now(timezone.utc).isoformat()
        profile.inviter_id = inviter_id
        profile.invited_at = now_iso

        # 更新推荐人邀请计数
        inviter_profile = await self.repo.get_profile_by_user(inviter_id)
        if inviter_profile:
            inviter_profile.total_invite_number += 1

        logger.info(
            "referral_admin_bound",
            user_id=str(user_id),
            inviter_id=str(inviter_id),
        )

    # --------------------------------------------------------------------------
    # 7. 管理员解绑
    # --------------------------------------------------------------------------
    async def admin_unbind(self, user_id: UUID) -> None:
        """管理员解除推荐关系"""
        profile = await self.repo.get_profile_by_user(user_id)
        if not profile:
            raise AppException(ReferralError.PROFILE_NOT_FOUND)

        if not profile.inviter_id:
            return  # 本来就没绑定

        old_inviter_id = profile.inviter_id

        # 清除绑定
        profile.inviter_id = None
        profile.invited_at = None

        # 递减推荐人邀请计数
        inviter_profile = await self.repo.get_profile_by_user(old_inviter_id)
        if inviter_profile and inviter_profile.total_invite_number > 0:
            inviter_profile.total_invite_number -= 1

        logger.info(
            "referral_admin_unbound",
            user_id=str(user_id),
            old_inviter_id=str(old_inviter_id),
        )
