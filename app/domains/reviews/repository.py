"""
File: app/domains/reviews/repository.py
Description: 评价数据访问层

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.review import OrderReview


class ReviewRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, review_id: UUID) -> Optional[OrderReview]:
        stmt = select(OrderReview).where(
            OrderReview.id == review_id,
            OrderReview.is_deleted.is_(False),
        )
        return await self.db.scalar(stmt)

    async def get_by_order_item(self, order_item_id: UUID) -> Optional[OrderReview]:
        """检查某个订单明细是否已评价"""
        stmt = select(OrderReview).where(
            OrderReview.order_item_id == order_item_id,
            OrderReview.is_deleted.is_(False),
        )
        return await self.db.scalar(stmt)

    async def list_by_product(
        self,
        product_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[OrderReview], int]:
        """某商品的评价列表（仅可见的）"""
        conditions = [
            OrderReview.product_id == product_id,
            OrderReview.is_visible.is_(True),
            OrderReview.is_deleted.is_(False),
        ]
        stmt = (
            select(OrderReview)
            .where(*conditions)
            .order_by(OrderReview.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = list((await self.db.scalars(stmt)).all())

        count_stmt = select(func.count()).select_from(OrderReview).where(*conditions)
        total: int = await self.db.scalar(count_stmt) or 0
        return rows, total

    async def list_by_user(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[OrderReview], int]:
        """我的评价列表"""
        conditions = [
            OrderReview.user_id == user_id,
            OrderReview.is_deleted.is_(False),
        ]
        stmt = (
            select(OrderReview)
            .where(*conditions)
            .order_by(OrderReview.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = list((await self.db.scalars(stmt)).all())

        count_stmt = select(func.count()).select_from(OrderReview).where(*conditions)
        total: int = await self.db.scalar(count_stmt) or 0
        return rows, total

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[OrderReview], int]:
        """B 端全量评价列表"""
        conditions = [OrderReview.is_deleted.is_(False)]
        stmt = (
            select(OrderReview)
            .where(*conditions)
            .order_by(OrderReview.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = list((await self.db.scalars(stmt)).all())

        count_stmt = select(func.count()).select_from(OrderReview).where(*conditions)
        total: int = await self.db.scalar(count_stmt) or 0
        return rows, total
