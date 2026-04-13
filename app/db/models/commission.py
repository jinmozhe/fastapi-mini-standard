"""
File: app/db/models/commission.py
Description: 佣金记录 ORM 模型

记录每笔订单产生的佣金明细：谁的消费 → 给谁分佣 → 多少钱 → 什么状态。

佣金状态：
- frozen   → 已冻结（佣金在推荐人的 frozen_balance 中，等订单完成释放）
- settled  → 已结算（已释放到推荐人的 balance 中，可提现）
- revoked  → 已撤销（管理员强制取消订单，从 frozen_balance 扣回）

Author: jinmozhe
Created: 2026-04-13
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import UUIDModel


class CommissionRecord(UUIDModel):
    """佣金记录表"""

    __tablename__ = "commission_records"

    # 关联订单
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="关联订单 ID",
    )

    # 订单编号（冗余，方便展示查询）
    order_no: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="订单编号"
    )

    # 下单买家
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="下单买家 ID",
    )

    # 佣金受益人
    beneficiary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="佣金受益人 ID",
    )

    # 佣金层级: first(直推) / second(间推) / other(其它)
    commission_level: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="佣金层级: first/second/other"
    )

    # 佣金金额
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="佣金金额"
    )

    # 佣金状态: frozen / settled / revoked
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="佣金状态: frozen/settled/revoked"
    )

    # 冻结时间
    frozen_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="冻结时间(ISO格式)"
    )

    # 结算时间（释放到可用余额）
    settled_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="结算时间(ISO格式)"
    )

    # 撤销时间
    revoked_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="撤销时间(ISO格式)"
    )

    # 撤销原因
    revoke_reason: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="撤销原因"
    )
