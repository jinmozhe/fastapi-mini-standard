"""
File: app/domains/user_wallets/schemas.py
Description: 用户钱包领域的 Pydantic 请求与响应验证模型

Author: jinmozhe
Created: 2026-04-12
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.user_wallets.constants import BalanceChangeType, PointChangeType


# ------------------------------------------------------------------------------
# 钱包表检视模型
# ------------------------------------------------------------------------------


class UserWalletRead(BaseModel):
    """用户钱包查询返回信息"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    balance: Decimal = Field(..., description="可用资金余额", max_digits=15, decimal_places=2)
    frozen_balance: Decimal = Field(..., description="冻结资金", max_digits=15, decimal_places=2)
    points: int = Field(..., description="当前可用积分")
    version: int = Field(..., description="乐观锁版本")
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------------------
# 流水表检视模型
# ------------------------------------------------------------------------------


class BalanceLogRead(BaseModel):
    """资金流水记录信息"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    change_type: BalanceChangeType = Field(..., description="变动类型")
    amount: Decimal = Field(..., description="变动金额")
    before_balance: Decimal = Field(..., description="变动前余额")
    after_balance: Decimal = Field(..., description="变动后余额")
    ref_id: UUID | None = Field(default=None, description="关联业务ID")
    remark: str | None = Field(default=None, description="变动备注")
    created_at: datetime


class PointLogRead(BaseModel):
    """积分流水记录信息"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    change_type: PointChangeType = Field(..., description="变动类型")
    points: int = Field(..., description="变动积分")
    before_points: int = Field(..., description="变动前积分")
    after_points: int = Field(..., description="变动后积分")
    ref_id: UUID | None = Field(default=None, description="关联业务ID")
    remark: str | None = Field(default=None, description="变动备注")
    created_at: datetime


# ------------------------------------------------------------------------------
# B端 后台管理操作请求模型
# ------------------------------------------------------------------------------


class AdminChangeBalanceReq(BaseModel):
    """B端手工充值/扣款资金请求"""

    amount: Annotated[Decimal, Field(..., gt=0, decimal_places=2, max_digits=15, description="变动金额 (必须为正数)")]
    remark: Annotated[str, Field(..., min_length=2, max_length=150, description="操作原因/备注")]


class AdminChangePointsReq(BaseModel):
    """B端手工派发/回收积分请求"""

    points: Annotated[int, Field(..., gt=0, description="变动积分 (必须为正数)")]
    remark: Annotated[str, Field(..., min_length=2, max_length=150, description="操作原因/备注")]
