"""
File: app/domains/refunds/repository.py
Description: 售后退款数据访问层

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.refund import RefundRecord


class RefundRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, refund_id: UUID) -> Optional[RefundRecord]:
        """按 ID 查退款记录"""
        stmt = select(RefundRecord).where(
            RefundRecord.id == refund_id,
            RefundRecord.is_deleted.is_(False),
        )
        return await self.db.scalar(stmt)

    async def get_active_by_order(self, order_id: UUID) -> Optional[RefundRecord]:
        """查订单是否有进行中的退款（pending / approved / returning）"""
        stmt = select(RefundRecord).where(
            RefundRecord.order_id == order_id,
            RefundRecord.status.in_(["pending", "approved", "returning"]),
            RefundRecord.is_deleted.is_(False),
        )
        return await self.db.scalar(stmt)

    async def list_by_user(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[RefundRecord], int]:
        """C 端：买家的退款列表"""
        conditions = [
            RefundRecord.user_id == user_id,
            RefundRecord.is_deleted.is_(False),
        ]
        stmt = (
            select(RefundRecord)
            .where(*conditions)
            .order_by(RefundRecord.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = list((await self.db.scalars(stmt)).all())

        count_stmt = select(func.count()).select_from(RefundRecord).where(*conditions)
        total: int = await self.db.scalar(count_stmt) or 0
        return rows, total

    async def list_all(
        self,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[RefundRecord], int]:
        """B 端：全量退款列表"""
        conditions = [RefundRecord.is_deleted.is_(False)]
        if status:
            conditions.append(RefundRecord.status == status)

        stmt = (
            select(RefundRecord)
            .where(*conditions)
            .order_by(RefundRecord.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = list((await self.db.scalars(stmt)).all())

        count_stmt = select(func.count()).select_from(RefundRecord).where(*conditions)
        total: int = await self.db.scalar(count_stmt) or 0
        return rows, total
