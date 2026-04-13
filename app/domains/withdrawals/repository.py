"""
File: app/domains/withdrawals/repository.py
Description: 提现数据访问层

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.withdrawal import WithdrawalRecord


class WithdrawalRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, withdrawal_id: UUID) -> Optional[WithdrawalRecord]:
        stmt = select(WithdrawalRecord).where(
            WithdrawalRecord.id == withdrawal_id,
            WithdrawalRecord.is_deleted.is_(False),
        )
        return await self.db.scalar(stmt)

    async def get_pending_by_user(self, user_id: UUID) -> Optional[WithdrawalRecord]:
        """查用户是否有待审核的提现"""
        stmt = select(WithdrawalRecord).where(
            WithdrawalRecord.user_id == user_id,
            WithdrawalRecord.status.in_(["pending", "approved"]),
            WithdrawalRecord.is_deleted.is_(False),
        )
        return await self.db.scalar(stmt)

    async def list_by_user(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[WithdrawalRecord], int]:
        """C 端：我的提现记录"""
        conditions = [
            WithdrawalRecord.user_id == user_id,
            WithdrawalRecord.is_deleted.is_(False),
        ]
        stmt = (
            select(WithdrawalRecord)
            .where(*conditions)
            .order_by(WithdrawalRecord.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = list((await self.db.scalars(stmt)).all())

        count_stmt = select(func.count()).select_from(WithdrawalRecord).where(*conditions)
        total: int = await self.db.scalar(count_stmt) or 0
        return rows, total

    async def list_all(
        self,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[WithdrawalRecord], int]:
        """B 端：全量提现列表"""
        conditions = [WithdrawalRecord.is_deleted.is_(False)]
        if status:
            conditions.append(WithdrawalRecord.status == status)

        stmt = (
            select(WithdrawalRecord)
            .where(*conditions)
            .order_by(WithdrawalRecord.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = list((await self.db.scalars(stmt)).all())

        count_stmt = select(func.count()).select_from(WithdrawalRecord).where(*conditions)
        total: int = await self.db.scalar(count_stmt) or 0
        return rows, total
