"""
File: app/domains/orders/schemas.py
Description: 订单领域输入/输出验证模型

Author: jinmozhe
Created: 2026-04-13
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 结算预览
# ==============================================================================

class CheckoutPreviewReq(BaseModel):
    """结算预览请求"""
    cart_item_ids: list[UUID] = Field(..., min_length=1, description="购物车条目 ID 列表")
    address_id: UUID = Field(..., description="收货地址 ID")


class CheckoutItemPreview(BaseModel):
    """结算预览中的单个商品项"""
    product_id: UUID
    sku_id: UUID | None = None
    product_name: str
    product_image: str
    sku_spec: dict | None = None
    unit_price: Decimal
    quantity: int
    subtotal: Decimal
    weight: Decimal = Field(default=Decimal("0.00"), description="重量(克)")


class CheckoutPreviewResult(BaseModel):
    """结算预览结果"""
    items: list[CheckoutItemPreview]
    address: dict  # AddressSnapshot
    items_amount: Decimal
    freight_amount: Decimal
    total_amount: Decimal


# ==============================================================================
# 提交订单
# ==============================================================================

class OrderCreateReq(BaseModel):
    """提交订单请求"""
    cart_item_ids: list[UUID] = Field(..., min_length=1, description="购物车条目 ID 列表")
    address_id: UUID = Field(..., description="收货地址 ID")
    remark: str | None = Field(default=None, max_length=200, description="买家留言")


class OrderCreateResult(BaseModel):
    """提交订单结果"""
    order_id: UUID
    order_no: str
    total_amount: Decimal
    status: str


# ==============================================================================
# 去支付
# ==============================================================================

class OrderPayReq(BaseModel):
    """去支付请求"""
    payment_method: str = Field(..., description="支付方式: wechat / balance")


# ==============================================================================
# 订单响应
# ==============================================================================

class OrderItemRead(BaseModel):
    """订单明细响应"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    sku_id: UUID | None
    product_snapshot: dict
    sku_snapshot: dict | None
    unit_price: Decimal
    quantity: int
    subtotal: Decimal


class CommissionRecordRead(BaseModel):
    """佣金记录响应"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    buyer_id: UUID
    beneficiary_id: UUID
    commission_level: str
    amount: Decimal
    status: str
    frozen_at: str | None
    settled_at: str | None
    revoked_at: str | None


class OrderDetailRead(BaseModel):
    """订单详情响应（含明细 + 佣金）"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_no: str
    user_id: UUID
    status: str
    address_snapshot: dict
    items_amount: Decimal
    freight_amount: Decimal
    total_amount: Decimal
    commission_total: Decimal
    payment_method: str | None
    paid_at: str | None
    shipping_company: str | None
    tracking_number: str | None
    shipped_at: str | None
    completed_at: str | None
    cancelled_at: str | None
    cancel_reason: str | None
    remark: str | None
    items: list[OrderItemRead] = Field(default_factory=list)
    commissions: list[CommissionRecordRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class OrderListItem(BaseModel):
    """订单列表项"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_no: str
    status: str
    items_amount: Decimal
    freight_amount: Decimal
    total_amount: Decimal
    commission_total: Decimal
    payment_method: str | None
    item_count: int = Field(default=0, description="商品种类数")
    # 首个商品快照（列表卡片展示用）
    first_item_snapshot: dict | None = None
    created_at: datetime


class OrderPageResult(BaseModel):
    """订单分页结果"""
    items: list[OrderListItem]
    total: int
    page: int
    page_size: int


# ==============================================================================
# B 端发货
# ==============================================================================

class OrderShipReq(BaseModel):
    """发货请求"""
    shipping_company: str = Field(..., min_length=1, max_length=50, description="快递公司")
    tracking_number: str = Field(..., min_length=1, max_length=50, description="运单号")


# ==============================================================================
# B 端强制取消
# ==============================================================================

class OrderForceCancelReq(BaseModel):
    """强制取消请求"""
    cancel_reason: str = Field(..., min_length=1, max_length=200, description="取消原因")
