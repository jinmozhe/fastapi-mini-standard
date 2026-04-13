"""
File: app/domains/orders/repository.py
Description: 订单数据访问层

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.commission import CommissionRecord
from app.db.models.order import Order, OrderItem


class OrderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, order_id: UUID) -> Optional[Order]:
        """按 ID 查订单"""
        stmt = select(Order).where(
            Order.id == order_id,
            Order.is_deleted.is_(False),
        )
        return await self.db.scalar(stmt)

    async def get_by_order_no(self, order_no: str) -> Optional[Order]:
        """按订单编号查"""
        stmt = select(Order).where(
            Order.order_no == order_no,
            Order.is_deleted.is_(False),
        )
        return await self.db.scalar(stmt)

    async def get_items(self, order_id: UUID) -> list[OrderItem]:
        """获取订单明细"""
        stmt = (
            select(OrderItem)
            .where(OrderItem.order_id == order_id)
            .order_by(OrderItem.created_at.asc())
        )
        return list((await self.db.scalars(stmt)).all())

    async def list_by_user(
        self,
        user_id: UUID,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Order], int]:
        """C 端：用户的订单列表"""
        conditions = [
            Order.user_id == user_id,
            Order.is_deleted.is_(False),
        ]
        if status:
            conditions.append(Order.status == status)

        stmt = (
            select(Order)
            .where(*conditions)
            .order_by(Order.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = list((await self.db.scalars(stmt)).all())

        count_stmt = select(func.count()).select_from(Order).where(*conditions)
        total: int = await self.db.scalar(count_stmt) or 0

        return rows, total

    async def list_all(
        self,
        status: str | None = None,
        user_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Order], int]:
        """B 端：全量订单列表"""
        conditions = [Order.is_deleted.is_(False)]
        if status:
            conditions.append(Order.status == status)
        if user_id:
            conditions.append(Order.user_id == user_id)

        stmt = (
            select(Order)
            .where(*conditions)
            .order_by(Order.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = list((await self.db.scalars(stmt)).all())

        count_stmt = select(func.count()).select_from(Order).where(*conditions)
        total: int = await self.db.scalar(count_stmt) or 0

        return rows, total

    async def count_items(self, order_id: UUID) -> int:
        """统计订单商品种类数"""
        stmt = (
            select(func.count())
            .select_from(OrderItem)
            .where(OrderItem.order_id == order_id)
        )
        return await self.db.scalar(stmt) or 0

    async def get_first_item(self, order_id: UUID) -> Optional[OrderItem]:
        """获取订单第一条明细（列表卡片展示用）"""
        stmt = (
            select(OrderItem)
            .where(OrderItem.order_id == order_id)
            .order_by(OrderItem.created_at.asc())
            .limit(1)
        )
        return await self.db.scalar(stmt)


class CommissionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_order(self, order_id: UUID) -> list[CommissionRecord]:
        """获取订单关联的全部佣金记录"""
        stmt = (
            select(CommissionRecord)
            .where(CommissionRecord.order_id == order_id)
            .order_by(CommissionRecord.created_at.asc())
        )
        return list((await self.db.scalars(stmt)).all())

    async def get_frozen_by_order(self, order_id: UUID) -> list[CommissionRecord]:
        """获取订单中状态为 frozen 的佣金记录（取消时批量扣回）"""
        stmt = select(CommissionRecord).where(
            CommissionRecord.order_id == order_id,
            CommissionRecord.status == "frozen",
        )
        return list((await self.db.scalars(stmt)).all())
