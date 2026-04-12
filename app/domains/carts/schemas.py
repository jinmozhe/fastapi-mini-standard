"""
File: app/domains/carts/schemas.py
Description: 购物车输入与输出验证模型

Author: jinmozhe
Created: 2026-04-12
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.products.schemas import ProductRead, ProductSkuRead


class CartItemAddReq(BaseModel):
    """加车 / 扣车请求（通过数量增减实现加减车）"""
    product_id: UUID = Field(..., description="商品ID")
    sku_id: Optional[UUID] = Field(default=None, description="SKU_ID")
    quantity: int = Field(default=1, gt=0, description="加入数量（正数）")


class CartItemPatchReq(BaseModel):
    """购物车单项局部修改 (数量或勾选状态)"""
    quantity: Optional[int] = Field(default=None, gt=0, description="直接修改为确切数字")
    selected: Optional[bool] = Field(default=None, description="修改勾选转态")


class CartItemDeleteReq(BaseModel):
    """通过 IDs 批量移出购物车"""
    ids: list[UUID] = Field(..., min_length=1, description="购物车单项主键合集")


class CartItemMergeReq(BaseModel):
    """(废弃通过本接口，计划交由全局 Header 抓取实现。目前仅为占位)"""
    pass


class CartItemRead(BaseModel):
    """
    带全量计价算后的购物车完美响应。
    此结构体的数据全部从内存装配拼接而来，非单一对象属性映射。
    """
    id: UUID
    product_id: UUID
    sku_id: Optional[UUID]
    quantity: int
    selected: bool
    
    # 【核心动态装配点】
    is_valid: bool = Field(..., description="商品是否依旧有效（未删、且仍在售）")
    realtime_price: Decimal = Field(..., description="引擎嗅探出的此刻的最终买入单价")
    is_stock_ok: bool = Field(..., description="当前要求的数量是否超过了实时库存限制")
    member_tag: Optional[str] = Field(default=None, description="命中的特权签标")
    
    # 前端用于展示的包裹壳子
    product: ProductRead
    sku: Optional[ProductSkuRead]
