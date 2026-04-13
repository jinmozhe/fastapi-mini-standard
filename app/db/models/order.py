"""
File: app/db/models/order.py
Description: 订单体系 ORM 模型

包含 2 个模型：
1. Order      - 订单主表
2. OrderItem  - 订单明细表（商品快照）

设计原则：
- address_snapshot / product_snapshot / sku_snapshot 均为 JSONB 快照，与源表完全解耦
- order_items 不加商品/SKU 外键，仅保留 ID 用于跳转
- 订单支持 5 状态机：pending_payment → pending_shipment → shipped → completed / cancelled

Author: jinmozhe
Created: 2026-04-13
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import SoftDeleteMixin, UUIDModel


class Order(UUIDModel, SoftDeleteMixin):
    """
    订单主表

    status 状态机：
    - pending_payment   → 待付款（用户可自助取消）
    - pending_shipment  → 待发货（已支付，仅管理员可强制取消）
    - shipped           → 已发货（仅管理员可强制取消）
    - completed         → 已完成（不可取消）
    - cancelled         → 已取消
    """

    __tablename__ = "orders"

    # 订单编号（唯一）
    order_no: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, comment="订单编号"
    )

    # 买家
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="买家 ID",
    )

    # 订单状态
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending_payment",
        server_default=text("'pending_payment'"),
        comment="订单状态",
    )

    # --------------------------------------------------------------------------
    # 地址快照（JSONB，与 addresses 表完全解耦）
    # --------------------------------------------------------------------------
    address_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, comment="收货地址快照"
    )

    # --------------------------------------------------------------------------
    # 金额
    # --------------------------------------------------------------------------

    # 商品总价
    items_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="商品总价"
    )

    # 运费
    freight_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
        comment="运费",
    )

    # 应付金额 = items_amount + freight_amount
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="应付金额"
    )

    # 佣金汇总（冗余，方便列表展示）
    commission_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
        comment="该订单产生的佣金总额",
    )

    # --------------------------------------------------------------------------
    # 支付信息（支付后填入）
    # --------------------------------------------------------------------------

    payment_method: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="支付方式: wechat / balance"
    )

    paid_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="支付成功时间(ISO格式)"
    )

    # --------------------------------------------------------------------------
    # 物流信息（发货后填入）
    # --------------------------------------------------------------------------

    shipping_company: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="快递公司"
    )

    tracking_number: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="运单号"
    )

    shipped_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="发货时间"
    )

    # --------------------------------------------------------------------------
    # 完成/取消
    # --------------------------------------------------------------------------

    completed_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="确认收货时间"
    )

    cancelled_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="取消时间"
    )

    cancel_reason: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="取消原因"
    )

    # 取消操作人（用户自助取消 = user_id，管理员强制取消 = admin_id）
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="取消操作人 ID"
    )

    # 买家留言
    remark: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="买家留言"
    )


class OrderItem(UUIDModel):
    """
    订单明细表

    product_snapshot / sku_snapshot 为 JSONB 快照，
    记录下单瞬间的商品信息，与 products / product_skus 表解耦。
    """

    __tablename__ = "order_items"

    # 所属订单
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属订单 ID",
    )

    # 商品 ID（用于跳转，非外键）
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, comment="商品 ID"
    )

    # SKU ID（用于跳转，非外键；无 SKU 商品为 NULL）
    sku_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="SKU ID"
    )

    # 商品快照
    product_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, comment="商品快照 { name, main_image, product_type }"
    )

    # SKU 快照（无 SKU 时为 NULL）
    sku_snapshot: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="SKU 快照 { sku_code, spec_values, image_url, weight }"
    )

    # 下单时单价（5级引擎计算结果）
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="下单时单价"
    )

    # 数量
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="购买数量"
    )

    # 小计 = unit_price × quantity
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="小计"
    )
