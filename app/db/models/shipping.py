"""
File: app/db/models/shipping.py
Description: 运费模板 ORM 模型

包含 2 个模型：
1. ShippingTemplate       - 运费模板主表（计价方式、包邮门槛）
2. ShippingTemplateRegion  - 地区阶梯运费规则（首重/续重、省份匹配）

设计原则：
- 每个实体商品关联一个运费模板（products.shipping_template_id）
- 模板内包含 N 条地区规则，结算时按收货地址 province_code 精确匹配
- province_codes 为空数组 [] 的规则为"其余地区"兜底规则（每个模板必须有一条）
- 计价方式支持 weight（按重量/克）和 piece（按件数）
- 虚拟商品 / 包邮商品不关联模板（shipping_template_id = NULL）

Author: jinmozhe
Created: 2026-04-13
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import SoftDeleteMixin, UUIDModel


class ShippingTemplate(UUIDModel, SoftDeleteMixin):
    """
    运费模板主表

    pricing_method:
    - 'weight'：按重量计价（首重/续重，单位：克）
    - 'piece'：按件数计价（首件/续件）

    free_shipping_threshold:
    - NULL：不设包邮优惠（永远收运费）
    - 0：永远包邮
    - 99.00：满 99 元包邮

    free_shipping_exclude_regions:
    - 包邮政策排除的省份编码数组（如新疆/西藏）
    - 即使满额也不包邮的地区
    """

    __tablename__ = "shipping_templates"

    # 模板名称
    name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="模板名称"
    )

    # 计价方式: weight / piece
    pricing_method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="weight",
        server_default=text("'weight'"),
        comment="计价方式: weight(按重量) / piece(按件数)",
    )

    # 满额包邮门槛（NULL = 不设包邮）
    free_shipping_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="满额包邮门槛（NULL=不设包邮，0=永远包邮）",
    )

    # 包邮排除地区（省份编码数组）
    free_shipping_exclude_regions: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'[]'::jsonb"),
        comment='包邮排除的省份编码 ["650000","540000"]',
    )

    # 是否启用
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
        comment="是否启用",
    )


class ShippingTemplateRegion(UUIDModel):
    """
    地区阶梯运费规则

    province_codes 匹配逻辑：
    - ["310000","320000","330000"] → 匹配上海/江苏/浙江
    - [] (空数组) → 兜底规则：匹配其余未列出的所有地区（每个模板必须有一条）

    计价公式（按重量示例）：
    运费 = first_unit_price + ⌈(总重量 - first_unit) / additional_unit⌉ × additional_unit_price
    """

    __tablename__ = "shipping_template_regions"

    # 所属模板
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipping_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属运费模板 ID",
    )

    # 地区名称（仅展示用）
    region_name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="地区名称（如 江浙沪皖）"
    )

    # 省份行政编码数组（空数组 = 其余地区兜底）
    province_codes: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment='省份编码数组 ["310000","320000"]，空数组=其余地区',
    )

    # 首重(克) / 首件(件)
    first_unit: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="首重(克)/首件(件)"
    )

    # 首重/首件费用
    first_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="首重/首件费用"
    )

    # 续重(克) / 续件(件)
    additional_unit: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="续重(克)/续件(件)"
    )

    # 每续重/续件费用
    additional_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="每续重/续件费用"
    )
