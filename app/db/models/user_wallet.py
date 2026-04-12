"""
File: app/db/models/user_wallet.py
Description: 用户钱包体系，包含资金与积分钱包、资金流水、积分流水。

建立独立的钱包表、通过乐观锁防止并发更新超卖。资金流水和积分流水分离。

Author: jinmozhe
Created: 2026-04-12
"""

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, Integer, Numeric, String, ForeignKey
from sqlalchemy.orm import Mapped, declared_attr, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.models.base import SoftDeleteMixin, UUIDModel


class UserWallet(UUIDModel, SoftDeleteMixin):
    """
    用户钱包模型
    包含资金余额、冻结资金、积分，以及乐观锁版本号
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "user_wallets"

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return (
            # 防御负数余额（防止扣款穿透引发资金安全事故）
            CheckConstraint("balance >= 0", name="ck_wallet_balance_positive"),
            CheckConstraint("frozen_balance >= 0", name="ck_wallet_frozen_positive"),
            CheckConstraint("points >= 0", name="ck_wallet_points_positive"),
        )

    # 关联用户：1对1关系，但在模型层遵循 No-Relationship 规范仅设定外键
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
        comment="归属用户ID",
    )

    # 资金余额 (单位：元，精度2位，最大千亿级)
    balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="当前可用现金余额",
    )

    # 冻结余额 (如提现中)
    frozen_balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="提现审核等冻结的余额",
    )

    # 积分
    points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="当前可用总积分",
    )

    # 乐观锁版本号 (非常重要，实现高并发无损扣减)
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="乐观锁版本号",
    )


class UserBalanceLog(UUIDModel):
    """
    资金变动日志 (铁账本)
    详细记录每笔现金进出，保障财务对账与追击
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "user_balance_logs"

    # 关联用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True,
        nullable=False,
        comment="归属用户ID",
    )

    # 变动类型枚举值
    change_type: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
        comment="变动类型(如order_pay/commission_first)",
    )

    # 变动金额: 负数表示扣除(支出)，正数表示增加(收入)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="变动金额(+/-)",
    )

    # 变动前余额快照
    before_balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="变动前余额",
    )

    # 变动后余额快照
    after_balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="变动后余额",
    )

    # 外部关联单号 (如订单ID、退款单ID等)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        index=True,
        nullable=True,
        comment="关联的业务单据ID",
    )

    # 备注描述
    remark: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="变动备注/原因说明",
    )


class UserPointLog(UUIDModel):
    """
    积分变动日志 (铁账本)
    积分变动单独建表，避免影响资金表的吞吐以及方便设置独立的到期清理策略
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "user_point_logs"

    # 关联用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True,
        nullable=False,
        comment="归属用户ID",
    )

    # 变动类型枚举值
    change_type: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
        comment="变动类型(如sign_in/order_complete)",
    )

    # 变动积分: 负数=扣除，正数=增加
    points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="变动积分(+/-)",
    )

    # 变动前积分快照
    before_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="变动前积分",
    )

    # 变动后积分快照
    after_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="变动后积分",
    )

    # 外部关联单号
    ref_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        index=True,
        nullable=True,
        comment="关联的业务单据ID",
    )

    # 备注描述
    remark: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="变动备注/原因说明",
    )
