"""
File: app/domains/reviews/schemas.py
Description: 评价领域 Schema

Author: jinmozhe
Created: 2026-04-13
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreateReq(BaseModel):
    """提交评价请求"""
    order_id: UUID = Field(..., description="订单 ID")
    order_item_id: UUID = Field(..., description="订单明细 ID")
    rating: int = Field(..., ge=1, le=5, description="评分 1-5")
    content: str = Field(..., min_length=1, max_length=500, description="评价内容")
    images: list[str] | None = Field(default=None, max_length=9, description="评价图片 URL")
    is_anonymous: bool = Field(default=False, description="是否匿名")


class ReviewRead(BaseModel):
    """评价响应"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    order_item_id: UUID
    user_id: UUID
    product_id: UUID
    rating: int
    content: str
    images: list | None
    is_anonymous: bool
    reply_content: str | None
    replied_at: str | None
    created_at: datetime


class ReviewPageResult(BaseModel):
    """评价分页"""
    items: list[ReviewRead]
    total: int
    page: int
    page_size: int


class ReviewReplyReq(BaseModel):
    """商家回复请求"""
    reply_content: str = Field(..., min_length=1, max_length=500, description="回复内容")


class ReviewVisibilityReq(BaseModel):
    """设置评价可见性"""
    is_visible: bool = Field(..., description="是否展示")
