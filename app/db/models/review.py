"""
File: app/db/models/review.py
Description: 订单评价 ORM 模型

评价规则：
- 仅 completed 状态的订单可评价
- 每个 order_item 只能评价一次
- 评价后不可修改

Author: jinmozhe
Created: 2026-04-13
"""

import uuid

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import SoftDeleteMixin, UUIDModel


class OrderReview(UUIDModel, SoftDeleteMixin):
    """订单评价表"""

    __tablename__ = "order_reviews"

    # 关联订单
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id"),
        nullable=False,
        index=True,
        comment="关联订单 ID",
    )

    # 关联订单明细（按商品评价）
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="关联订单明细 ID",
    )

    # 评价用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="评价用户 ID",
    )

    # 商品 ID（冗余，聚合展示用）
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="商品 ID",
    )

    # 评分（1-5 星）
    rating: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="评分 1-5 星"
    )

    # 评价内容
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="评价内容"
    )

    # 评价图片
    images: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, comment="评价图片 URL 列表"
    )

    # 匿名评价
    is_anonymous: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
        comment="是否匿名",
    )

    # 商家回复
    reply_content: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="商家回复内容"
    )

    # 回复时间
    replied_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="回复时间"
    )

    # 是否展示（管理员可隐藏）
    is_visible: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
        comment="是否展示",
    )
