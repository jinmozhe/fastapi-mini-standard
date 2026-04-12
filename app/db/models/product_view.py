"""
File: app/db/models/product_view.py
Description: 已登录买家的商品浏览足迹快照模型

Author: jinmozhe
Created: 2026-04-12
"""

import uuid
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import UUIDModel


class ProductView(UUIDModel):
    """
    (表名: product_views) 足迹橱窗表
    仅收集并展示真实买家的商品历史纪录。通过 UPSERT 技术实现一条记录的最近阅览时间刷新。
    """
    __tablename__ = "product_views"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        comment="访客 ID",
        index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), 
        nullable=False, 
        comment="被浏览商品的 SPU ID"
    )

    __table_args__ = (
        # 联合唯一索引：确保一个用户看一台设备只有唯一的一条抽屉档。
        # 这是进行 Upsert 操作的核心基础。
        UniqueConstraint("user_id", "product_id", name="uq_product_views_user_product"),
    )
    # 注: UUIDModel 自带的 updated_at 将会完美充当 "最近浏览时间 (viewed_at)"。
