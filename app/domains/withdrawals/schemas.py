"""
File: app/domains/withdrawals/schemas.py
Description: 提现领域 Schema

Author: jinmozhe
Created: 2026-04-13
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# C 端
# ==============================================================================

class WithdrawApplyReq(BaseModel):
    """申请提现请求"""
    amount: Decimal = Field(..., gt=0, max_digits=15, decimal_places=2, description="提现金额")
    channel: str = Field(..., description="提现通道: balance_to_wechat / balance_to_bank / balance_to_alipay")
    account_info: dict | None = Field(default=None, description="收款账号信息")
    remark: str | None = Field(default=None, max_length=200, description="备注")


class WithdrawApplyResult(BaseModel):
    """申请提现结果"""
    withdrawal_id: UUID
    withdrawal_no: str
    amount: Decimal
    fee: Decimal
    actual_amount: Decimal
    status: str


class WithdrawalDetailRead(BaseModel):
    """提现详情"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    withdrawal_no: str
    user_id: UUID
    amount: Decimal
    fee: Decimal
    actual_amount: Decimal
    channel: str
    account_info: dict | None
    status: str
    admin_remark: str | None
    remark: str | None
    reviewed_at: str | None
    completed_at: str | None
    rejected_at: str | None
    created_at: datetime
    updated_at: datetime


class WithdrawalListItem(BaseModel):
    """提现列表项"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    withdrawal_no: str
    amount: Decimal
    fee: Decimal
    actual_amount: Decimal
    channel: str
    status: str
    created_at: datetime


class WithdrawalPageResult(BaseModel):
    """提现分页"""
    items: list[WithdrawalListItem]
    total: int
    page: int
    page_size: int


# ==============================================================================
# B 端
# ==============================================================================

class WithdrawalReviewReq(BaseModel):
    """审核提现"""
    action: str = Field(..., description="approve / reject")
    admin_remark: str | None = Field(default=None, max_length=200, description="审核备注")
