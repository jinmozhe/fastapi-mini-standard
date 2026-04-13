"""
File: app/db/models/refund.py
Description: 退款记录 ORM 模型

售后状态机：
- pending    → 待审核
- approved   → 已通过（仅退款时直接执行退款；退货退款时等买家寄回）
- returning  → 退货中（买家已填退货单号，等商家确认收货）
- refunded   → 已退款
- rejected   → 已驳回

Author: jinmozhe
Created: 2026-04-13
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    ForeignKey,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import SoftDeleteMixin, UUIDModel


class RefundRecord(UUIDModel, SoftDeleteMixin):
    """退款记录表"""

    __tablename__ = "refund_records"

    # 退款单号（唯一）
    refund_no: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, comment="退款单号"
    )

    # 关联订单
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id"),
        nullable=False,
        index=True,
        comment="关联订单 ID",
    )

    # 订单编号（冗余展示）
    order_no: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="订单编号"
    )

    # 买家
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="买家 ID",
    )

    # 退款类型: refund_only（仅退款）/ return_refund（退货退款）
    refund_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="退款类型: refund_only/return_refund"
    )

    # 退款金额
    refund_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="退款金额"
    )

    # 退款原因
    reason: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="退款原因"
    )

    # 详细说明
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="详细说明"
    )

    # 凭证图片
    images: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, comment="凭证图片 URL 列表"
    )

    # 退款状态
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="退款状态: pending/approved/returning/refunded/rejected",
    )

    # 管理员审核备注
    admin_remark: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="管理员审核备注"
    )

    # 退货运单号（退货退款时买家填写）
    return_tracking_no: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="退货运单号"
    )

    # 退货快递公司
    return_company: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="退货快递公司"
    )

    # 审核通过时间
    approved_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="审核通过时间"
    )

    # 退款完成时间
    refunded_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="退款完成时间"
    )

    # 驳回时间
    rejected_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="驳回时间"
    )
