"""
File: app/db/models/cart.py
Description: 购物车持久层模型

Author: jinmozhe
Created: 2026-04-12
"""

import uuid
from sqlalchemy import Boolean, ForeignKey, Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import UUIDModel


class CartItem(UUIDModel):
    """
    购物车单项记录
    支持严格游客双轨制（实名为辅，游客为主时的挂载）。
    绝不落地保存购买单价，单价均通过外键连接引擎实时重算核销。
    """
    __tablename__ = "cart_items"

    # 双轨身份
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=True, 
        comment="实名归属（与 anonymous_id 必有一填）"
    )
    anonymous_id: Mapped[str | None] = mapped_column(
        String(128), 
        nullable=True, 
        comment="游客设备的唯一特征指纹"
    )

    # 实体防丢与挂载
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), 
        nullable=False
    )
    sku_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_skus.id", ondelete="CASCADE"), 
        nullable=True,
        comment="如果商品带变体必选"
    )

    # 控制变量
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="件数"
    )
    selected: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="UI 选定结算状态"
    )

    __table_args__ = (
        Index("ix_cart_items_user_or_anon", "user_id", "anonymous_id"),
    )
