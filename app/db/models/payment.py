"""
File: app/db/models/payment.py
Description: 支付记录 ORM 模型

设计原则：
- 每笔订单对应一条支付记录（1:1）
- payment_no 为系统内部唯一流水号，也作为微信支付的 out_trade_no
- 余额支付即时完成，微信支付需等待异步回调确认
- order_id 暂不加外键约束（订单表尚未建立），靠应用层保证一致性

Author: jinmozhe
Created: 2026-04-13
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import UUIDModel


class PaymentRecord(UUIDModel):
    """
    支付记录表

    status 状态机：
    - pending     → 待支付（微信支付已发起，等待回调）
    - paid        → 已支付
    - closed      → 已关闭（超时未支付 / 用户取消）
    - refunding   → 退款中（已发起退款请求）
    - refunded    → 已退款
    """

    __tablename__ = "payment_records"

    # 系统内部支付流水号（兼用作微信支付的 out_trade_no，≤32字符）
    payment_no: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, comment="支付流水号"
    )

    # 关联订单（暂不加 FK，订单表尚未建立）
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="关联订单 ID",
    )

    # 支付用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="支付用户 ID",
    )

    # 支付方式: wechat / balance
    payment_method: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="支付方式: wechat / balance"
    )

    # 支付金额
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="支付金额"
    )

    # 支付状态
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="支付状态: pending/paid/closed/refunding/refunded",
    )

    # --------------------------------------------------------------------------
    # 微信支付专属字段（余额支付时为 NULL）
    # --------------------------------------------------------------------------

    # 微信预支付交易会话标识（用于前端调起支付）
    wechat_prepay_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="微信预支付 prepay_id"
    )

    # 微信支付订单号（回调时填入）
    wechat_transaction_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="微信支付交易号"
    )

    # --------------------------------------------------------------------------
    # 支付/退款时间
    # --------------------------------------------------------------------------

    # 支付成功时间（余额支付即时填入，微信支付回调时填入）
    paid_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="支付成功时间(ISO格式)"
    )

    # 退款金额
    refund_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True, comment="退款金额"
    )

    # 退款时间
    refunded_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="退款时间(ISO格式)"
    )

    # 备注/失败原因
    remark: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="备注/失败原因"
    )
