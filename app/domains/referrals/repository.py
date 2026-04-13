"""
File: app/domains/referrals/repository.py
Description: 推荐关系数据访问层

Author: jinmozhe
Created: 2026-04-13
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.models.user_level import UserLevel, UserLevelProfile


class ReferralRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile_by_user(self, user_id: UUID) -> Optional[UserLevelProfile]:
        """按 user_id 查 Profile"""
        stmt = select(UserLevelProfile).where(UserLevelProfile.user_id == user_id)
        return await self.db.scalar(stmt)

    async def get_profile_by_invite_code(self, invite_code: str) -> Optional[UserLevelProfile]:
        """按邀请码查 Profile"""
        stmt = select(UserLevelProfile).where(
            UserLevelProfile.invite_code == invite_code
        )
        return await self.db.scalar(stmt)

    async def get_user(self, user_id: UUID) -> Optional[User]:
        """查用户"""
        return await self.db.get(User, user_id)

    async def get_direct_invitees(
        self,
        inviter_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """查询某用户的直接下级（一级团队）"""
        conditions = [UserLevelProfile.inviter_id == inviter_id]

        # 计数
        count_stmt = select(func.count()).select_from(UserLevelProfile).where(*conditions)
        total: int = await self.db.scalar(count_stmt) or 0

        # 分页查询，联表取用户信息和等级名
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

    async def get_all_direct_invitee_ids(self, inviter_id: UUID) -> list[UUID]:
        """查所有直接下级的 user_id 列表（不分页，用于递推）"""
        stmt = select(UserLevelProfile.user_id).where(
            UserLevelProfile.inviter_id == inviter_id
        )
        result = await self.db.scalars(stmt)
        return list(result.all())

    async def get_team_stats_for_level(self, invitee_ids: list[UUID]) -> tuple[int, Decimal]:
        """统计一组用户的人数和总消费"""
        if not invitee_ids:
            return 0, Decimal("0.00")

        count = len(invitee_ids)
        stmt = select(func.coalesce(func.sum(UserLevelProfile.total_consume), 0)).where(
            UserLevelProfile.user_id.in_(invitee_ids)
        )
        total_consume = await self.db.scalar(stmt) or Decimal("0.00")
        return count, Decimal(str(total_consume))

    async def is_in_chain(self, user_id: UUID, target_id: UUID, max_depth: int = 10) -> bool:
        """
        检查 target_id 是否在 user_id 的上级链中（防循环）。
        从 user_id 往上追溯，看是否能追到 target_id。
        """
        current = user_id
        for _ in range(max_depth):
            stmt = select(UserLevelProfile.inviter_id).where(
                UserLevelProfile.user_id == current
            )
            inviter = await self.db.scalar(stmt)
            if not inviter:
                return False
            if inviter == target_id:
                return True
            current = inviter
        return False
