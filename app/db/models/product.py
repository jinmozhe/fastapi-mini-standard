"""
File: app/db/models/product.py
Description: 商品体系 ORM 模型

包含 7 个模型：
1. Category              - 商品分类（树形，最多3级）
2. Product               - 商品主表 (SPU)
3. ProductCategory       - 商品-分类多对多关联
4. ProductSpec           - 规格模板
5. ProductSku            - SKU 变体（独立价格+库存）
6. ProductLevelPrice     - 商品级会员固定售价
7. ProductLevelCommission - 商品级独立固定分佣

架构原则：
- 分类级折扣/分佣规则以 JSONB 存于 categories 表（与 user_levels 的 JSONB 规则模式一致）
- 商品级价格/分佣为独立表（精确到 SKU 级控制）
- 无 SKU 商品的库存和成本价在 products 表，有 SKU 时在 product_skus 表
- 价格引擎 5 级优先级：SKU级固定价 → 商品级固定价 → 分类级折扣 → 等级折扣 → 原价
- 分佣引擎 3 级优先级：商品级固定佣 → 分类级百分比佣 → 等级通用佣

Author: jinmozhe
Created: 2026-04-12
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import SoftDeleteMixin, UUIDModel


# ==============================================================================
# 1. 商品分类（树形，最多 3 级）
# ==============================================================================


class Category(UUIDModel):
    """
    商品分类表

    支持无限层级树形结构（业务层限制最多 3 级）。
    level_prices / level_commissions 存储分类级别的会员等级折扣和分佣百分比规则。
    """

    __tablename__ = "categories"

    # 分类名称
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="分类名称"
    )

    # 父分类（null = 顶层分类）
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        comment="父分类 ID",
    )

    # 分类图标
    icon_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="分类图标 URL"
    )

    # 排序权重
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
        comment="排序权重（越大越前）",
    )

    # 是否启用
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
        comment="是否启用",
    )

    # --------------------------------------------------------------------------
    # 分类级会员等级规则 (JSONB)
    # --------------------------------------------------------------------------

    # 分类级等级折扣率
    # 结构: [{"level_id": "uuid", "discount_rate": 0.9500}, ...]
    level_prices: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='分类级等级折扣率 [{"level_id":"uuid","discount_rate":0.95}]',
    )

    # 分类级等级百分比分佣
    # 结构: [{"level_id": "uuid", "first_rate": 0.03, "second_rate": 0.02, "other_rate": 0.01}]
    level_commissions: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='分类级等级百分比分佣 [{"level_id":"uuid","first_rate":0.03,...}]',
    )


# ==============================================================================
# 2. 商品主表 (SPU)
# ==============================================================================


class Product(UUIDModel, SoftDeleteMixin):
    """
    商品主表（SPU 级）

    product_type 为必填字段，创建商品时必须选择 virtual 或 physical。
    无 SKU 商品的库存（stock）和成本价（cost_price）使用本表字段；
    有 SKU 时，库存和成本价来自各 SKU 记录，本表的被忽略。
    """

    __tablename__ = "products"

    # 商品标题
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="商品标题"
    )

    # 副标题 / 卖点
    subtitle: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="副标题/卖点"
    )

    # 商品类型：virtual(虚拟) / physical(实体)，创建时必选
    product_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="商品类型: virtual / physical"
    )

    # 商品主图 URL
    main_image: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="商品主图 URL"
    )

    # 轮播图 URL 数组
    images: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'[]'::jsonb"),
        comment="轮播图 URL 数组",
    )

    # 富文本详情
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="商品详情（富文本）"
    )

    # 市场价（划线价）
    market_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="市场价（划线价）"
    )

    # 本店售价（无 SKU 时为实际售价，有 SKU 时为参考展示价）
    base_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="本店售价"
    )

    # 成本价（无 SKU 时使用）
    cost_price: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True, comment="成本价（无 SKU 时使用）"
    )

    # 库存（无 SKU 时使用）
    stock: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="库存（无 SKU 时使用）"
    )

    # 上架状态: draft / on_sale / off_sale
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
        comment="上架状态: draft / on_sale / off_sale",
    )

    # 排序权重
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
        comment="排序权重",
    )

    # 累计销量（冗余计数）
    sales_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
        comment="累计销量",
    )

    # 关联运费模板（NULL = 包邮/虚拟商品不参与运费计算）
    shipping_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipping_templates.id", ondelete="SET NULL"),
        nullable=True,
        comment="运费模板 ID（NULL=包邮/虚拟商品）",
    )


# ==============================================================================
# 3. 商品-分类多对多关联
# ==============================================================================


class ProductCategory(UUIDModel):
    """商品与分类的多对多关联表"""

    __tablename__ = "product_categories"

    __table_args__ = (
        UniqueConstraint("product_id", "category_id", name="uq_product_category"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        comment="商品 ID",
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        comment="分类 ID",
    )


# ==============================================================================
# 4. 规格模板
# ==============================================================================


class ProductSpec(UUIDModel):
    """
    商品规格模板

    定义规格维度及候选值，为 SKU 笛卡尔积生成提供数据源。
    示例: spec_name="颜色", spec_values=["红色","蓝色","白色"]
    """

    __tablename__ = "product_specs"

    __table_args__ = (
        UniqueConstraint("product_id", "spec_name", name="uq_product_spec_name"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        comment="归属商品 ID",
    )

    spec_name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="规格名称（如颜色、尺寸）"
    )

    spec_values: Mapped[list] = mapped_column(
        JSONB, nullable=False, comment='候选值数组 ["红色","蓝色","白色"]'
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
        comment="展示顺序",
    )


# ==============================================================================
# 5. SKU 变体（独立价格 + 库存）
# ==============================================================================


class ProductSku(UUIDModel):
    """
    SKU 变体表

    每个 SKU 是规格维度的一个确定组合，拥有完全独立的售价和库存。
    示例: spec_values={"颜色":"红色","尺寸":"XL"}, price=109.00, stock=56
    """

    __tablename__ = "product_skus"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="归属商品 ID",
    )

    # SKU 唯一编码
    sku_code: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, comment="SKU 唯一编码"
    )

    # 规格组合快照
    spec_values: Mapped[dict] = mapped_column(
        JSONB, nullable=False, comment='规格组合 {"颜色":"红色","尺寸":"XL"}'
    )

    # 该 SKU 的独立售价
    price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="SKU 独立售价"
    )

    # 成本价
    cost_price: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True, comment="成本价"
    )

    # 库存
    stock: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
        comment="库存数量",
    )

    # SKU 专属图片
    image_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="SKU 专属图片"
    )

    # 是否启用
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
        comment="是否启用",
    )

    # SKU 重量（克），用于运费计算。0 或 NULL 表示虚拟商品不参与运费
    weight: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0.00"),
        server_default=text("0.00"),
        nullable=False,
        comment="重量（克），用于运费计算",
    )

    # 排序
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
        comment="显示顺序",
    )


# ==============================================================================
# 6. 商品级会员固定售价
# ==============================================================================


class ProductLevelPrice(UUIDModel):
    """
    会员等级专属固定售价

    存储固定金额（不是折扣比例），优先级高于分类级折扣和等级通用折扣。
    sku_id 为 null 时表示商品级（对所有 SKU 生效）。
    """

    __tablename__ = "product_level_prices"

    __table_args__ = (
        UniqueConstraint(
            "product_id", "sku_id", "level_id",
            name="uq_product_sku_level_price",
        ),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        comment="归属商品 ID",
    )

    # null = 商品级（对所有 SKU 生效）
    sku_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_skus.id", ondelete="CASCADE"),
        nullable=True,
        comment="指定 SKU（null = 商品级）",
    )

    level_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_levels.id", ondelete="CASCADE"),
        nullable=False,
        comment="会员等级 ID",
    )

    # 固定售价
    price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="该等级的固定售价"
    )


# ==============================================================================
# 7. 商品级独立固定分佣
# ==============================================================================


class ProductLevelCommission(UUIDModel):
    """
    商品级独立分佣覆盖

    优先级高于分类级百分比分佣和等级通用分佣。
    使用固定金额（不是百分比），与 user_levels.commission_rules 的 first/second/other 三层一致。
    """

    __tablename__ = "product_level_commissions"

    __table_args__ = (
        UniqueConstraint(
            "product_id", "level_id",
            name="uq_product_level_commission",
        ),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        comment="归属商品 ID",
    )

    level_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_levels.id", ondelete="CASCADE"),
        nullable=False,
        comment="推荐人等级 ID",
    )

    # 直推佣金固定金额
    commission_first: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="直推佣金固定金额"
    )

    # 间推佣金固定金额
    commission_second: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=Decimal("0.00"),
        server_default=text("0.00"),
        nullable=False,
        comment="间推佣金固定金额",
    )

    # 其它层级佣金固定金额
    commission_other: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=Decimal("0.00"),
        server_default=text("0.00"),
        nullable=False,
        comment="其它层级佣金固定金额",
    )
