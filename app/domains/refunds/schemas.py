"""
File: app/domains/refunds/schemas.py
Description: 售后退款领域 Schema

Author: jinmozhe
Created: 2026-04-13
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# C 端：申请退款
# ==============================================================================

class RefundApplyReq(BaseModel):
    """申请退款请求"""
    order_id: UUID = Field(..., description="订单 ID")
    refund_type: str = Field(..., description="退款类型: refund_only / return_refund")
    refund_amount: Decimal = Field(..., gt=0, max_digits=15, decimal_places=2, description="退款金额")
    reason: str = Field(..., min_length=1, max_length=200, description="退款原因")
    description: str | None = Field(default=None, max_length=1000, description="详细说明")
    images: list[str] | None = Field(default=None, max_length=9, description="凭证图片 URL 列表")


class RefundApplyResult(BaseModel):
    """申请退款结果"""
    refund_id: UUID
    refund_no: str
    status: str


# ==============================================================================
# C 端：填退货单号
# ==============================================================================

class ReturnShippingReq(BaseModel):
    """填退货运单号"""
    return_company: str = Field(..., min_length=1, max_length=50, description="快递公司")
    return_tracking_no: str = Field(..., min_length=1, max_length=50, description="运单号")


# ==============================================================================
# B 端：审核
# ==============================================================================

class RefundReviewReq(BaseModel):
    """审核退款请求"""
    action: str = Field(..., description="approve / reject")
    admin_remark: str | None = Field(default=None, max_length=200, description="审核备注")


# ==============================================================================
# 退款详情响应
# ==============================================================================

class RefundDetailRead(BaseModel):
    """退款详情"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    refund_no: str
    order_id: UUID
    order_no: str
    user_id: UUID
    refund_type: str
    refund_amount: Decimal
    reason: str
    description: str | None
    images: list | None
    status: str
    admin_remark: str | None
    return_tracking_no: str | None
    return_company: str | None
    approved_at: str | None
    refunded_at: str | None
    rejected_at: str | None
    created_at: datetime
    updated_at: datetime


class RefundListItem(BaseModel):
    """退款列表项"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    refund_no: str
    order_no: str
    refund_type: str
    refund_amount: Decimal
    reason: str
    status: str
    created_at: datetime


class RefundPageResult(BaseModel):
    """退款分页"""
    items: list[RefundListItem]
    total: int
    page: int
    page_size: int
