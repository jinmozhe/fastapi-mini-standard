"""
File: app/domains/user_levels/repository.py
Description: 用户等级领域仓储层 (Repository)

负责 UserLevel / UserLevelProfile / UserLevelRecord 的数据库访问操作。

Author: jinmozhe
Created: 2026-04-12
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user_level import UserLevel, UserLevelProfile, UserLevelRecord


class UserLevelRepository:
    """等级配置表仓储"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_active(self) -> list[UserLevel]:
        """获取所有启用的等级 (按 rank_weight 升序)"""
        stmt = (
            select(UserLevel)
            .where(UserLevel.is_active.is_(True))
            .order_by(UserLevel.rank_weight.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all(self) -> list[UserLevel]:
        """获取所有等级 (含停用，按 rank_weight 升序)"""
        stmt = select(UserLevel).order_by(UserLevel.rank_weight.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, level_id: uuid.UUID) -> UserLevel | None:
        """根据 ID 获取等级"""
        stmt = select(UserLevel).where(UserLevel.id == level_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> UserLevel | None:
        """根据名称查询等级 (用于唯一性校验)"""
        stmt = select(UserLevel).where(UserLevel.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_rank_weight(self, rank_weight: int) -> UserLevel | None:
        """根据权重查询等级 (用于唯一性校验)"""
        stmt = select(UserLevel).where(UserLevel.rank_weight == rank_weight)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, level: UserLevel) -> UserLevel:
        """创建等级"""
        self.session.add(level)
        await self.session.flush()
        return level

    async def delete(self, level: UserLevel) -> None:
        """物理删除等级"""
        await self.session.delete(level)
        await self.session.flush()


class UserLevelProfileRepository:
    """会员资产与进度表仓储"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> UserLevelProfile | None:
        """根据用户 ID 获取等级档案"""
        stmt = select(UserLevelProfile).where(UserLevelProfile.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, profile: UserLevelProfile) -> UserLevelProfile:
        """创建等级档案"""
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def count_by_level_id(self, level_id: uuid.UUID) -> int:
        """统计某个等级下的用户数"""
        stmt = (
            select(func.count())
            .select_from(UserLevelProfile)
            .where(UserLevelProfile.level_id == level_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()


class UserLevelRecordRepository:
    """升降级历史表仓储"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, record: UserLevelRecord) -> UserLevelRecord:
        """创建升降级记录"""
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_by_user_id(
        self, user_id: uuid.UUID, limit: int = 20
    ) -> list[UserLevelRecord]:
        """获取用户的升降级历史 (最新在前)"""
        stmt = (
            select(UserLevelRecord)
            .where(UserLevelRecord.user_id == user_id)
            .order_by(UserLevelRecord.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
