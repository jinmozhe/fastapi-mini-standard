"""
File: app/db/models/user_level.py
Description: C端用户等级体系 ORM 模型

包含 3 张表：
1. UserLevel       - 等级规则配置表 (B端维护)
2. UserLevelProfile - 会员资产与进度表 (1:1 独立解耦)
3. UserLevelRecord  - 升降级历史流水表

架构原则：
- 等级体系完全独立于 users 核心认证表，通过 user_id 外键关联
- 升级规则 (upgrade_rules) 采用 JSONB AST 规则树，支持 AND/OR 任意组合
- 分佣规则 (commission_rules) 和奖励规则 (reward_rules) 采用 JSONB 数组，支持 % 百分比与固定金额混用
- inviter_id 推荐关系存储在 user_level_profiles 中，不污染核心账号表

Author: jinmozhe
Created: 2026-04-12
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import UUIDModel


# ------------------------------------------------------------------------------
# 1. 等级规则配置表 (由 B端管理员维护)
# ------------------------------------------------------------------------------

class UserLevel(UUIDModel):
    """
    会员等级配置表

    关键设计：
    - upgrade_rules: JSONB 规则树引擎，支持 AND/OR 嵌套组合
      示例: {"op":"AND","conditions":[{"metric":"total_consume","operator":">=","value":10000}]}
    - commission_rules: 额外级分佣规则数组，rank 对应下级等级的 rank_weight
      示例: [{"rank":1,"first":"3%","second":"2%","other":"1"}]
    - reward_rules: 下级升级奖励规则数组，结构同 commission_rules
    """
    __tablename__ = "user_levels"

    # 等级名称 (如 五星会员、六星会员)
    name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="等级名称"
    )

    # 动态升级规则树 (JSONB AST)
    upgrade_rules: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="升级规则 (JSONB AST 规则树，支持 AND/OR 嵌套)"
    )

    # 折扣率 (如 0.95 表示 95 折)
    discount_rate: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        default=Decimal("1.0000"),
        server_default=text("1.0000"),
        nullable=False,
        comment="折扣率 (如 0.95 = 95折)",
    )

    # 额外级分佣规则 (JSONB 数组)
    commission_rules: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, comment="分佣规则 [{'rank':1,'first':'3%','second':'2%','other':'1'}]"
    )

    # 下级升级奖励规则 (JSONB 数组)
    reward_rules: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, comment="升级奖励规则 [{'rank':2,'first':'100','second':'50','other':'10'}]"
    )

    # 等级图标
    icon_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="等级图标 URL"
    )

    # 富文本说明
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="等级权益说明 (富文本)"
    )

    # 等级排序权重 (数字越大级别越高，用于升降级比较)
    rank_weight: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False, comment="等级排序权重 (越大越高)"
    )

    # 是否启用
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
        comment="是否启用",
    )


# ------------------------------------------------------------------------------
# 2. 会员资产与进度表 (1:1 独立解耦，不污染 users 核心表)
# ------------------------------------------------------------------------------

class UserLevelProfile(UUIDModel):
    """
    会员资产与进度表

    关键设计：
    - 与 users 表 1:1 关联，通过 user_id UNIQUE 约束保证
    - inviter_id 记录推荐关系，用于额外级分佣链路追溯
    - total_* 字段为历史累加器指标，仅供升降级引擎判定使用
    - is_manual 为人工锁定标识，系统计算程序将跳过此用户
    """
    __tablename__ = "user_level_profiles"

    # 关联用户 (1:1 唯一约束)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="关联用户 ID",
    )

    # 当前所属等级
    level_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_levels.id", ondelete="SET NULL"),
        nullable=True,
        comment="当前等级 ID",
    )

    # 推荐人 ID (上级用户，用于额外级分佣链路追溯)
    inviter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="推荐人用户 ID (直接上级)",
    )

    # 人工强制锁定标识 (为 true 时系统升降级程序跳过此用户)
    is_manual: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
        comment="是否人工锁定等级 (跳过自动升降级)",
    )

    # --------------------------------------------------------------------------
    # 历史累加器指标 (仅供升降级规则引擎判定)
    # --------------------------------------------------------------------------

    # 累计消费净金额 (退款会扣减)
    total_consume: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=Decimal("0.00"),
        server_default=text("0.00"),
        nullable=False,
        comment="历史累计消费净金额",
    )

    # 累计获得积分 (历史总量，非当前可用)
    total_points: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
        comment="历史累计获得积分",
    )

    # 累计订单数 (退款订单会扣减)
    total_buy_number: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
        comment="历史累计订单数",
    )

    # 累计邀请人数
    total_invite_number: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
        comment="累计邀请注册人数",
    )


# ------------------------------------------------------------------------------
# 3. 升降级历史流水表
# ------------------------------------------------------------------------------

class UserLevelRecord(UUIDModel):
    """
    升降级历史纪要

    记录用户每次等级变动的快照，用于客服追查与数据分析。
    change_type: UPGRADE(系统自动升级) / DOWNGRADE(系统自动降级) / MANUAL(后台手工调整)
    """
    __tablename__ = "user_level_records"

    # 关联用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户 ID",
    )

    # 变动前等级 (新用户首次绑定时为空)
    old_level_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_levels.id", ondelete="SET NULL"),
        nullable=True,
        comment="变动前等级 ID",
    )

    # 变动后等级
    new_level_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_levels.id", ondelete="SET NULL"),
        nullable=False,
        comment="变动后等级 ID",
    )

    # 变动类型
    change_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="变动类型: UPGRADE / DOWNGRADE / MANUAL"
    )

    # 变动说明
    remark: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="变动说明"
    )
