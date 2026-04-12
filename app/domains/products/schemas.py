"""
File: app/domains/products/schemas.py
Description: 商品领域 Pydantic 请求与响应验证模型

Author: jinmozhe
Created: 2026-04-12
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.products.constants import ProductType

from app.domains.products.constants import ProductStatus, ProductType


# ==============================================================================
# 分类 Schemas
# ==============================================================================


class CategoryLevelPriceItem(BaseModel):
    """分类级等级折扣率规则项"""
    level_id: UUID = Field(..., description="会员等级 ID")
    discount_rate: Decimal = Field(..., gt=0, le=1, decimal_places=4, description="折扣率，如 0.9500 = 95折")


class CategoryLevelCommissionItem(BaseModel):
    """分类级等级百分比分佣规则项"""
    level_id: UUID = Field(..., description="会员等级 ID")
    first_rate: Decimal = Field(..., ge=0, le=1, decimal_places=4, description="直推佣金比例")
    second_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1, decimal_places=4, description="间推佣金比例")
    other_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1, decimal_places=4, description="其它层级佣金比例")


class CategoryCreate(BaseModel):
    """创建分类"""
    name: str = Field(..., min_length=1, max_length=100, description="分类名称")
    parent_id: UUID | None = Field(default=None, description="父分类 ID")
    icon_url: str | None = Field(default=None, max_length=500, description="图标 URL")
    sort_order: int = Field(default=0, description="排序")
    is_active: bool = Field(default=True, description="是否启用")
    level_prices: list[CategoryLevelPriceItem] | None = Field(default=None, description="等级折扣率")
    level_commissions: list[CategoryLevelCommissionItem] | None = Field(default=None, description="等级百分比分佣")


class CategoryUpdate(BaseModel):
    """更新分类"""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    parent_id: UUID | None = None
    icon_url: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    level_prices: list[CategoryLevelPriceItem] | None = None
    level_commissions: list[CategoryLevelCommissionItem] | None = None


class CategoryRead(BaseModel):
    """分类查询响应"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    parent_id: UUID | None
    icon_url: str | None
    sort_order: int
    is_active: bool
    level_prices: list | None = None
    level_commissions: list | None = None
    created_at: datetime
    updated_at: datetime


class CategoryTreeRead(CategoryRead):
    """分类树形结构（含子分类）"""
    children: list["CategoryTreeRead"] = []


# ==============================================================================
# 商品 Schemas
# ==============================================================================


class ProductCreate(BaseModel):
    """创建商品"""
    name: str = Field(..., min_length=1, max_length=200, description="商品标题")
    subtitle: str | None = Field(default=None, max_length=500, description="副标题")
    product_type: ProductType = Field(..., description="商品类型: virtual / physical")
    main_image: str = Field(..., max_length=500, description="主图 URL")
    images: list[str] | None = Field(default=None, description="轮播图 URL 数组")
    description: str | None = Field(default=None, description="富文本详情")
    market_price: Decimal = Field(..., gt=0, decimal_places=2, description="市场价")
    base_price: Decimal = Field(..., gt=0, decimal_places=2, description="本店售价")
    cost_price: Decimal | None = Field(default=None, ge=0, decimal_places=2, description="成本价（无SKU时必填）")
    stock: int | None = Field(default=None, ge=0, description="库存（无SKU时必填）")
    sort_order: int = Field(default=0, description="排序")
    category_ids: list[UUID] | None = Field(default=None, description="所属分类 ID 列表")


class ProductUpdate(BaseModel):
    """更新商品基本信息"""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    subtitle: str | None = None
    product_type: ProductType | None = None
    main_image: str | None = None
    images: list[str] | None = None
    description: str | None = None
    market_price: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    base_price: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    cost_price: Decimal | None = None
    stock: int | None = None
    sort_order: int | None = None


class ProductStatusUpdate(BaseModel):
    """更新商品状态"""
    status: ProductStatus = Field(..., description="目标状态")


class ProductRead(BaseModel):
    """商品查询响应"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    subtitle: str | None
    product_type: str
    main_image: str
    images: list | None
    description: str | None
    market_price: Decimal
    base_price: Decimal
    cost_price: Decimal | None
    stock: int | None
    status: str
    sort_order: int
    sales_count: int
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class ProductDetailRead(ProductRead):
    """商品详情（含 SKU 列表、规格、分类、价格信息）"""
    categories: list[CategoryRead] = []
    specs: list["ProductSpecRead"] = []
    skus: list["ProductSkuRead"] = []
    # 当前用户的价格信息
    display_price: Decimal | None = Field(default=None, description="当前用户最终售价")
    member_tag: str | None = Field(default=None, description="会员价标签（如'五星会员价'）")


# ==============================================================================
# 规格 Schemas
# ==============================================================================


class ProductSpecCreate(BaseModel):
    """规格模板项"""
    spec_name: str = Field(..., min_length=1, max_length=50, description="规格名")
    spec_values: list[str] = Field(..., min_length=1, description="候选值数组")
    sort_order: int = Field(default=0)


class ProductSpecRead(BaseModel):
    """规格模板查询响应"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    spec_name: str
    spec_values: list
    sort_order: int


# ==============================================================================
# SKU Schemas
# ==============================================================================


class ProductSkuCreate(BaseModel):
    """SKU 创建/更新项"""
    sku_code: str = Field(..., min_length=1, max_length=100, description="SKU 编码")
    spec_values: dict = Field(..., description='规格组合 {"颜色":"红色","尺寸":"XL"}')
    price: Decimal = Field(..., gt=0, decimal_places=2, description="SKU 独立售价")
    cost_price: Decimal | None = Field(default=None, ge=0, decimal_places=2, description="成本价")
    stock: int = Field(default=0, ge=0, description="库存")
    image_url: str | None = Field(default=None, max_length=500, description="SKU 专属图")
    is_active: bool = Field(default=True, description="是否启用")
    sort_order: int = Field(default=0)


class ProductSkuRead(BaseModel):
    """SKU 查询响应"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    sku_code: str
    spec_values: dict
    price: Decimal
    cost_price: Decimal | None
    stock: int
    image_url: str | None
    is_active: bool
    sort_order: int
    # 当前用户的等级价（如果有）
    display_price: Decimal | None = Field(default=None, description="当前用户该 SKU 最终售价")
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# 等级价 & 独立分佣 Schemas
# ==============================================================================


class ProductLevelPriceItem(BaseModel):
    """商品级等级固定价设置项"""
    sku_id: UUID | None = Field(default=None, description="SKU ID（null=商品级）")
    level_id: UUID = Field(..., description="会员等级 ID")
    price: Decimal = Field(..., gt=0, decimal_places=2, description="固定售价")


class ProductLevelCommissionItem(BaseModel):
    """商品级独立分佣设置项"""
    level_id: UUID = Field(..., description="推荐人等级 ID")
    commission_first: Decimal = Field(..., ge=0, decimal_places=2, description="直推佣金固定金额")
    commission_second: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2, description="间推佣金")
    commission_other: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2, description="其它层级佣金")


class BatchSetLevelPricesReq(BaseModel):
    """批量设置等级价"""
    items: list[ProductLevelPriceItem] = Field(..., description="等级价列表")


class BatchSetLevelCommissionsReq(BaseModel):
    """批量设置独立分佣"""
    items: list[ProductLevelCommissionItem] = Field(..., description="分佣列表")


class BatchSetCategoryIdsReq(BaseModel):
    """批量设置所属分类"""
    category_ids: list[UUID] = Field(..., description="分类 ID 列表")


class BatchSetSpecsReq(BaseModel):
    """批量设置规格模板"""
    specs: list[ProductSpecCreate] = Field(..., description="规格模板列表")


class BatchSetSkusReq(BaseModel):
    """批量设置 SKU"""
    skus: list[ProductSkuCreate] = Field(..., description="SKU 列表")


# ==============================================================================
# 商品浏览足迹表现层 (Product Views)
# ==============================================================================

class ProductViewItem(BaseModel):
    """商品足迹响应项"""
    viewed_at: datetime = Field(..., description="最近一次浏览的具体时钟")
    product: ProductRead = Field(..., description="浏览的商品外壳包裹")

