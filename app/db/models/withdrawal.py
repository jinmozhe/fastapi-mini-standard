"""
File: app/db/models/withdrawal.py
Description: 提现记录 ORM 模型

提现状态机：
- pending   → 待审核
- approved  → 已通过（打款中）
- completed → 已完成（到账）
- rejected  → 已驳回（退回余额）

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


class WithdrawalRecord(UUIDModel, SoftDeleteMixin):
    """提现记录表"""

    __tablename__ = "withdrawal_records"

    # 提现单号
    withdrawal_no: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, comment="提现单号"
    )

    # 申请用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="申请用户 ID",
    )

    # 提现金额
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="提现金额"
    )

    # 手续费（可配置为 0）
    fee: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
        comment="手续费",
    )

    # 实际到账金额 = amount - fee
    actual_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="实际到账金额"
    )

    # 提现通道: balance_to_wechat / balance_to_bank / balance_to_alipay
    channel: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="提现通道"
    )

    # 收款账号信息（JSONB 存储，如微信 openid / 银行卡号+开户行）
    account_info: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="收款账号信息",
    )

    # 提现状态
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="提现状态: pending/approved/completed/rejected",
    )

    # 管理员审核备注
    admin_remark: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="管理员审核备注"
    )

    # 审核人
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="审核人 ID"
    )

    # 审核时间
    reviewed_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="审核时间"
    )

    # 打款完成时间
    completed_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="打款完成时间"
    )

    # 驳回时间
    rejected_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="驳回时间"
    )

    # 用户备注
    remark: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="用户备注"
    )
