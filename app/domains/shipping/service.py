"""
File: app/domains/shipping/service.py
Description: 运费模板核心业务逻辑

包含：
- B 端模板 CRUD（创建/修改/删除/查询）
- 运费计算引擎（供订单结算域调用）

运费计算公式（按重量示例）：
  运费 = 首重费用 + ⌈(总重量 - 首重) / 续重⌉ × 续重费用
  若总重量 ≤ 首重，则运费 = 首重费用

Author: jinmozhe
Created: 2026-04-13
"""

import math
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.db.models.shipping import ShippingTemplate, ShippingTemplateRegion
from app.domains.shipping.constants import (
    VALID_PRICING_METHODS,
    ShippingError,
)
from app.domains.shipping.repository import ShippingTemplateRepository
from app.domains.shipping.schemas import (
    FreightResult,
    ShippingRegionItem,
    ShippingTemplateCreate,
    ShippingTemplateUpdate,
)


class ShippingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ShippingTemplateRepository(db)

    # --------------------------------------------------------------------------
    # B 端模板管理
    # --------------------------------------------------------------------------

    def _validate_regions(self, regions: list[ShippingRegionItem]) -> None:
        """校验地区规则：必须有兜底、省份不可重复"""
        has_default = False
        all_codes: set[str] = set()

        for region in regions:
            if not region.province_codes:
                has_default = True
            else:
                for code in region.province_codes:
                    if code in all_codes:
                        raise AppException(ShippingError.DUPLICATE_PROVINCE_CODE)
                    all_codes.add(code)

        if not has_default:
            raise AppException(ShippingError.MISSING_DEFAULT_REGION)

    async def create_template(self, data: ShippingTemplateCreate) -> ShippingTemplate:
        """创建运费模板（含地区规则）"""
        if data.pricing_method not in VALID_PRICING_METHODS:
            raise AppException(ShippingError.INVALID_PRICING_METHOD)

        self._validate_regions(data.regions)

        # 创建模板主体
        template = ShippingTemplate(
            name=data.name,
            pricing_method=data.pricing_method,
            free_shipping_threshold=data.free_shipping_threshold,
            free_shipping_exclude_regions=data.free_shipping_exclude_regions or [],
            is_active=True,
        )
        self.db.add(template)
        await self.db.flush()  # 拿到 template.id

        # 批量创建地区规则
        for item in data.regions:
            region = ShippingTemplateRegion(
                template_id=template.id,
                region_name=item.region_name,
                province_codes=item.province_codes,
                first_unit=item.first_unit,
                first_unit_price=item.first_unit_price,
                additional_unit=item.additional_unit,
                additional_unit_price=item.additional_unit_price,
            )
            self.db.add(region)

        return template

    async def update_template(self, template_id: UUID, data: ShippingTemplateUpdate) -> ShippingTemplate:
        """修改运费模板（全量替换地区规则）"""
        template = await self.repo.get_by_id(template_id)
        if not template:
            raise AppException(ShippingError.TEMPLATE_NOT_FOUND)

        if data.pricing_method not in VALID_PRICING_METHODS:
            raise AppException(ShippingError.INVALID_PRICING_METHOD)

        self._validate_regions(data.regions)

        # 更新模板主体
        template.name = data.name
        template.pricing_method = data.pricing_method
        template.free_shipping_threshold = data.free_shipping_threshold
        template.free_shipping_exclude_regions = data.free_shipping_exclude_regions or []

        # 先删后建：替换全部地区规则
        await self.repo.delete_regions(template_id)
        await self.db.flush()

        for item in data.regions:
            region = ShippingTemplateRegion(
                template_id=template_id,
                region_name=item.region_name,
                province_codes=item.province_codes,
                first_unit=item.first_unit,
                first_unit_price=item.first_unit_price,
                additional_unit=item.additional_unit,
                additional_unit_price=item.additional_unit_price,
            )
            self.db.add(region)

        return template

    async def delete_template(self, template_id: UUID) -> None:
        """软删除运费模板（校验是否有商品引用）"""
        template = await self.repo.get_by_id(template_id)
        if not template:
            raise AppException(ShippingError.TEMPLATE_NOT_FOUND)

        # 检查是否仍有商品引用
        product_count = await self.repo.count_products_using(template_id)
        if product_count > 0:
            raise AppException(ShippingError.TEMPLATE_IN_USE)

        template.is_deleted = True

    async def get_template_detail(self, template_id: UUID) -> dict:
        """获取模板详情（含地区规则）"""
        template = await self.repo.get_by_id(template_id)
        if not template:
            raise AppException(ShippingError.TEMPLATE_NOT_FOUND)

        regions = await self.repo.get_regions(template_id)
        return {"template": template, "regions": regions}

    # --------------------------------------------------------------------------
    # 运费计算引擎（供订单结算域调用）
    # --------------------------------------------------------------------------

    async def calculate_freight(
        self,
        template_id: UUID,
        province_code: str,
        total_weight_gram: Decimal,
        total_piece: int,
        subtotal: Decimal,
    ) -> FreightResult:
        """
        计算单个运费模板的运费。

        参数:
            template_id: 运费模板 ID
            province_code: 收货地址的省份行政编码
            total_weight_gram: 该模板下所有商品的总重量 (克)
            total_piece: 该模板下所有商品的总件数
            subtotal: 该模板下商品的小计金额（用于判断包邮条件）

        返回:
            FreightResult 包含运费金额和是否包邮
        """
        template = await self.repo.get_by_id(template_id)
        if not template:
            raise AppException(ShippingError.TEMPLATE_NOT_FOUND)

        # 1. 检查包邮条件
        if template.free_shipping_threshold is not None:
            exclude_regions = template.free_shipping_exclude_regions or []
            if subtotal >= template.free_shipping_threshold and province_code not in exclude_regions:
                return FreightResult(
                    template_id=template.id,
                    template_name=template.name,
                    freight=Decimal("0.00"),
                    is_free_shipping=True,
                )

        # 2. 加载地区规则
        regions = await self.repo.get_regions(template_id)

        # 3. 匹配地区规则（优先精确匹配，兜底空数组）
        matched_region: ShippingTemplateRegion | None = None
        default_region: ShippingTemplateRegion | None = None

        for region in regions:
            codes = region.province_codes or []
            if not codes:
                default_region = region
            elif province_code in codes:
                matched_region = region
                break

        rule = matched_region or default_region
        if not rule:
            # 理论上不会发生（校验保证有兜底），防御性编码
            return FreightResult(
                template_id=template.id,
                template_name=template.name,
                freight=Decimal("0.00"),
                is_free_shipping=False,
            )

        # 4. 计算运费
        if template.pricing_method == "weight":
            freight = self._calc_by_unit(
                total=total_weight_gram,
                first_unit=rule.first_unit,
                first_unit_price=rule.first_unit_price,
                additional_unit=rule.additional_unit,
                additional_unit_price=rule.additional_unit_price,
            )
        else:
            freight = self._calc_by_unit(
                total=Decimal(str(total_piece)),
                first_unit=rule.first_unit,
                first_unit_price=rule.first_unit_price,
                additional_unit=rule.additional_unit,
                additional_unit_price=rule.additional_unit_price,
            )

        return FreightResult(
            template_id=template.id,
            template_name=template.name,
            freight=freight,
            is_free_shipping=False,
        )

    @staticmethod
    def _calc_by_unit(
        total: Decimal,
        first_unit: Decimal,
        first_unit_price: Decimal,
        additional_unit: Decimal,
        additional_unit_price: Decimal,
    ) -> Decimal:
        """
        阶梯计价公式：
        运费 = 首重费 + ⌈(总量 - 首重) / 续重⌉ × 续重费
        若总量 ≤ 首重，则运费 = 首重费
        """
        if total <= first_unit:
            return first_unit_price

        overflow = total - first_unit
        # 向上取整：不满一个续重单位也按一个续重算
        additional_count = math.ceil(float(overflow) / float(additional_unit))
        freight = first_unit_price + Decimal(str(additional_count)) * additional_unit_price

        return freight
