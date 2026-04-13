"""
File: app/domains/fulfillment/schemas.py
Description: 履约领域输入/输出验证模型

Author: jinmozhe
Created: 2026-04-13
"""

from uuid import UUID

from pydantic import BaseModel, Field


class ShipOrderReq(BaseModel):
    """单个发货请求"""
    shipping_company: str = Field(..., min_length=1, max_length=50, description="快递公司")
    tracking_number: str = Field(..., min_length=1, max_length=50, description="运单号")


class BatchShipItem(BaseModel):
    """批量发货中的单个条目"""
    order_id: UUID = Field(..., description="订单 ID")
    shipping_company: str = Field(..., min_length=1, max_length=50, description="快递公司")
    tracking_number: str = Field(..., min_length=1, max_length=50, description="运单号")


class BatchShipReq(BaseModel):
    """批量发货请求"""
    items: list[BatchShipItem] = Field(..., min_length=1, max_length=100, description="发货列表")


class BatchShipResultItem(BaseModel):
    """批量发货单条结果"""
    order_id: UUID
    success: bool
    message: str = ""


class BatchShipResult(BaseModel):
    """批量发货结果"""
    total: int
    success_count: int
    fail_count: int
    details: list[BatchShipResultItem]


class AutoConfirmResult(BaseModel):
    """自动确认收货结果"""
    confirmed_count: int = Field(..., description="本次自动确认的订单数")
    order_nos: list[str] = Field(default_factory=list, description="确认的订单编号")
