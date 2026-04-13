"""
File: app/domains/shipping/repository.py
Description: 运费模板数据访问层

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shipping import ShippingTemplate, ShippingTemplateRegion


class ShippingTemplateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, template_id: UUID) -> Optional[ShippingTemplate]:
        """按 ID 取模板"""
        stmt = select(ShippingTemplate).where(
            ShippingTemplate.id == template_id,
            ShippingTemplate.is_deleted.is_(False),
        )
        return await self.db.scalar(stmt)

    async def get_regions(self, template_id: UUID) -> list[ShippingTemplateRegion]:
        """获取模板的全部地区规则"""
        stmt = (
            select(ShippingTemplateRegion)
            .where(ShippingTemplateRegion.template_id == template_id)
            .order_by(ShippingTemplateRegion.created_at.asc())
        )
        return list((await self.db.scalars(stmt)).all())

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ShippingTemplate], int]:
        """分页查询模板列表"""
        base_cond = [ShippingTemplate.is_deleted.is_(False)]

        # 查记录
        stmt = (
            select(ShippingTemplate)
            .where(*base_cond)
            .order_by(ShippingTemplate.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = list((await self.db.scalars(stmt)).all())

        # 查总数
        count_stmt = select(func.count()).select_from(ShippingTemplate).where(*base_cond)
        total: int = await self.db.scalar(count_stmt) or 0

        return rows, total

    async def count_region(self, template_id: UUID) -> int:
        """统计模板地区规则条数"""
        stmt = (
            select(func.count())
            .select_from(ShippingTemplateRegion)
            .where(ShippingTemplateRegion.template_id == template_id)
        )
        return await self.db.scalar(stmt) or 0

    async def delete_regions(self, template_id: UUID) -> None:
        """删除模板下的全部地区规则（更新时先删再建）"""
        stmt = delete(ShippingTemplateRegion).where(
            ShippingTemplateRegion.template_id == template_id
        )
        await self.db.execute(stmt)

    async def count_products_using(self, template_id: UUID) -> int:
        """统计有多少商品引用了该模板（删除前检查）"""
        from app.db.models.product import Product
        stmt = (
            select(func.count())
            .select_from(Product)
            .where(
                Product.shipping_template_id == template_id,
                Product.is_deleted.is_(False),
            )
        )
        return await self.db.scalar(stmt) or 0
