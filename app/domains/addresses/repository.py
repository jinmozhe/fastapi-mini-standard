"""
File: app/domains/addresses/repository.py
Description: 收货地址数据访问层

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.address import UserAddress


class AddressRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user(self, user_id: UUID) -> list[UserAddress]:
        """获取用户全部地址（默认优先排序）"""
        stmt = (
            select(UserAddress)
            .where(UserAddress.user_id == user_id)
            .order_by(UserAddress.is_default.desc(), UserAddress.created_at.asc())
        )
        result = await self.db.scalars(stmt)
        return list(result.all())

    async def get_by_id(self, address_id: UUID, user_id: UUID) -> Optional[UserAddress]:
        """安全查询：必须同时匹配 address_id 和 user_id"""
        stmt = select(UserAddress).where(
            UserAddress.id == address_id,
            UserAddress.user_id == user_id,
        )
        return await self.db.scalar(stmt)

    async def get_default(self, user_id: UUID) -> Optional[UserAddress]:
        """取出默认地址"""
        stmt = select(UserAddress).where(
            UserAddress.user_id == user_id,
            UserAddress.is_default.is_(True),
        )
        return await self.db.scalar(stmt)

    async def count_by_user(self, user_id: UUID) -> int:
        """统计用户地址数量（容量限制校验）"""
        result = await self.get_by_user(user_id)
        return len(result)

    async def clear_default(self, user_id: UUID) -> None:
        """将该用户所有地址的 is_default 重置为 False"""
        stmt = (
            update(UserAddress)
            .where(UserAddress.user_id == user_id)
            .values(is_default=False)
        )
        await self.db.execute(stmt)

    async def promote_first_as_default(self, user_id: UUID) -> None:
        """
        将该用户按 created_at 最早的地址晋升为默认
        （用于删除默认地址后的智能补位）
        """
        stmt = (
            select(UserAddress)
            .where(UserAddress.user_id == user_id)
            .order_by(UserAddress.created_at.asc())
            .limit(1)
        )
        candidate = await self.db.scalar(stmt)
        if candidate:
            candidate.is_default = True

    # --------------------------------------------------------------------------
    # B 端管理员专用方法
    # --------------------------------------------------------------------------

    async def admin_list_all(
        self,
        user_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[UserAddress], int]:
        """
        B 端分页查询全量地址。
        可选按 user_id 过滤（精确匹配某个用户的全部地址）。
        返回 (记录列表, 总条数)。
        """
        # 动态构建过滤条件
        conditions = []
        if user_id:
            conditions.append(UserAddress.user_id == user_id)

        # 查记录
        stmt = (
            select(UserAddress)
            .where(*conditions)
            .order_by(UserAddress.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = list((await self.db.scalars(stmt)).all())

        # 查总数
        count_stmt = select(func.count()).select_from(UserAddress).where(*conditions)
        total: int = await self.db.scalar(count_stmt) or 0

        return rows, total
