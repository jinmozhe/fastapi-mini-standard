"""
File: app/domains/shipping/schemas.py
Description: 运费模板输入与输出验证模型

Author: jinmozhe
Created: 2026-04-13
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 地区规则 Schemas
# ==============================================================================

class ShippingRegionItem(BaseModel):
    """地区运费规则（创建/更新时使用）"""
    region_name: str = Field(..., min_length=1, max_length=50, description="地区名称（如 江浙沪皖）")
    province_codes: list[str] = Field(default_factory=list, description="省份编码数组，空数组=其余地区兜底")
    first_unit: Decimal = Field(..., gt=0, decimal_places=2, description="首重(克)/首件(件)")
    first_unit_price: Decimal = Field(..., ge=0, decimal_places=2, description="首重/首件费用")
    additional_unit: Decimal = Field(..., gt=0, decimal_places=2, description="续重(克)/续件(件)")
    additional_unit_price: Decimal = Field(..., ge=0, decimal_places=2, description="每续重/续件费用")


class ShippingRegionRead(BaseModel):
    """地区规则响应"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_id: UUID
    region_name: str
    province_codes: list[str]
    first_unit: Decimal
    first_unit_price: Decimal
    additional_unit: Decimal
    additional_unit_price: Decimal
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# 模板 Schemas
# ==============================================================================

class ShippingTemplateCreate(BaseModel):
    """创建运费模板（含地区规则）"""
    name: str = Field(..., min_length=1, max_length=50, description="模板名称")
    pricing_method: str = Field(default="weight", description="计价方式: weight / piece")
    free_shipping_threshold: Decimal | None = Field(default=None, ge=0, description="满额包邮门槛(NULL=不设)")
    free_shipping_exclude_regions: list[str] = Field(default_factory=list, description="包邮排除的省份编码")
    regions: list[ShippingRegionItem] = Field(..., min_length=1, description="地区运费规则（至少一条兜底）")


class ShippingTemplateUpdate(BaseModel):
    """修改运费模板（全量替换规则）"""
    name: str = Field(..., min_length=1, max_length=50)
    pricing_method: str = Field(default="weight")
    free_shipping_threshold: Decimal | None = Field(default=None, ge=0)
    free_shipping_exclude_regions: list[str] = Field(default_factory=list)
    regions: list[ShippingRegionItem] = Field(..., min_length=1)


class ShippingTemplateRead(BaseModel):
    """运费模板响应（含地区规则列表）"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    pricing_method: str
    free_shipping_threshold: Decimal | None
    free_shipping_exclude_regions: list[str] | None
    is_active: bool
    regions: list[ShippingRegionRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ShippingTemplateListItem(BaseModel):
    """模板列表项（不含地区规则详情）"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    pricing_method: str
    free_shipping_threshold: Decimal | None
    is_active: bool
    region_count: int = Field(default=0, description="地区规则条数")
    created_at: datetime


class ShippingTemplatePageResult(BaseModel):
    """模板分页结果"""
    items: list[ShippingTemplateListItem]
    total: int
    page: int
    page_size: int


# ==============================================================================
# 运费计算结果（供结算域消费）
# ==============================================================================

class FreightResult(BaseModel):
    """单个运费模板的运费计算结果"""
    template_id: UUID
    template_name: str
    freight: Decimal = Field(description="运费金额（0 = 包邮）")
    is_free_shipping: bool = Field(description="是否命中包邮条件")
