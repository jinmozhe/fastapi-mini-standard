"""
File: app/domains/reviews/service.py
Description: 评价核心业务逻辑

Author: jinmozhe
Created: 2026-04-13
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.logging import logger
from app.db.models.review import OrderReview
from app.domains.orders.constants import OrderStatus
from app.domains.orders.repository import OrderRepository
from app.domains.reviews.constants import ReviewError
from app.domains.reviews.repository import ReviewRepository
from app.domains.reviews.schemas import ReviewCreateReq


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ReviewRepository(db)
        self.order_repo = OrderRepository(db)

    async def create_review(self, user_id: UUID, data: ReviewCreateReq) -> OrderReview:
        """
        提交评价。

        校验：
        1. 订单存在且属于当前用户
        2. 订单状态为 completed
        3. 指定的 order_item 属于该订单
        4. 该 order_item 未被评价过
        """
        order = await self.order_repo.get_by_id(data.order_id)
        if not order or order.user_id != user_id:
            raise AppException(ReviewError.ORDER_NOT_FOUND)

        if order.status != OrderStatus.COMPLETED:
            raise AppException(ReviewError.ORDER_NOT_COMPLETED)

        # 校验 order_item 属于该订单
        items = await self.order_repo.get_items(order.id)
        item = next((i for i in items if i.id == data.order_item_id), None)
        if not item:
            raise AppException(ReviewError.ITEM_NOT_FOUND)

        # 检查是否已评价
        existing = await self.repo.get_by_order_item(data.order_item_id)
        if existing:
            raise AppException(ReviewError.ALREADY_REVIEWED)

        review = OrderReview(
            order_id=order.id,
            order_item_id=data.order_item_id,
            user_id=user_id,
            product_id=item.product_id,
            rating=data.rating,
            content=data.content,
            images=data.images,
            is_anonymous=data.is_anonymous,
        )
        self.db.add(review)
        await self.db.flush()

        logger.info(
            "review_created",
            order_no=order.order_no,
            product_id=str(item.product_id),
            rating=data.rating,
        )
        return review

    async def reply_review(
        self,
        review_id: UUID,
        reply_content: str,
    ) -> None:
        """商家回复评价"""
        review = await self.repo.get_by_id(review_id)
        if not review:
            raise AppException(ReviewError.NOT_FOUND)

        now_iso = datetime.now(timezone.utc).isoformat()
        review.reply_content = reply_content
        review.replied_at = now_iso

        logger.info("review_replied", review_id=str(review_id))

    async def set_visibility(self, review_id: UUID, is_visible: bool) -> None:
        """管理员设置评价可见性"""
        review = await self.repo.get_by_id(review_id)
        if not review:
            raise AppException(ReviewError.NOT_FOUND)

        review.is_visible = is_visible
        logger.info(
            "review_visibility_changed",
            review_id=str(review_id),
            is_visible=is_visible,
        )
