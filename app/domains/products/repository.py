"""
File: app/domains/products/repository.py
Description: 商品领域数据持久化仓储层

Author: jinmozhe
Created: 2026-04-12
"""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import (
    Category,
    Product,
    ProductCategory,
    ProductLevelCommission,
    ProductLevelPrice,
    ProductSku,
    ProductSpec,
)


class CategoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.model = Category

    async def get_by_id(self, category_id: UUID) -> Category | None:
        return await self.db.get(Category, category_id)

    async def get_all_active(self) -> list[Category]:
        stmt = (
            select(Category)
            .where(Category.is_active.is_(True))
            .order_by(Category.sort_order.desc(), Category.created_at)
        )
        result = await self.db.scalars(stmt)
        return list(result.all())

    async def get_all(self) -> list[Category]:
        stmt = select(Category).order_by(Category.sort_order.desc(), Category.created_at)
        result = await self.db.scalars(stmt)
        return list(result.all())

    async def get_children_count(self, category_id: UUID) -> int:
        """获取直接子分类数量"""
        stmt = select(Category).where(Category.parent_id == category_id)
        result = await self.db.scalars(stmt)
        return len(list(result.all()))

    async def get_depth(self, category_id: UUID) -> int:
        """追溯 parent_id 链计算当前节点深度（顶层 = 1）"""
        depth = 0
        current_id = category_id
        while current_id is not None:
            depth += 1
            cat = await self.db.get(Category, current_id)
            if cat is None:
                break
            current_id = cat.parent_id
        return depth


class ProductRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.model = Product

    async def get_by_id(self, product_id: UUID) -> Product | None:
        return await self.db.get(Product, product_id)

    async def get_list(
        self,
        *,
        category_id: UUID | None = None,
        product_type: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        include_deleted: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Product]:
        stmt = select(Product)

        if not include_deleted:
            stmt = stmt.where(Product.is_deleted.is_(False))
        if status:
            stmt = stmt.where(Product.status == status)
        if product_type:
            stmt = stmt.where(Product.product_type == product_type)
        if keyword:
            stmt = stmt.where(Product.name.ilike(f"%{keyword}%"))
        if category_id:
            # 通过关联表过滤
            stmt = stmt.where(
                Product.id.in_(
                    select(ProductCategory.product_id).where(
                        ProductCategory.category_id == category_id
                    )
                )
            )

        stmt = stmt.order_by(Product.sort_order.desc(), Product.created_at.desc())
        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.scalars(stmt)
        return list(result.all())


class ProductCategoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_categories_for_product(self, product_id: UUID) -> list[Category]:
        """获取商品的所有关联分类"""
        stmt = (
            select(Category)
            .join(ProductCategory, ProductCategory.category_id == Category.id)
            .where(ProductCategory.product_id == product_id)
        )
        result = await self.db.scalars(stmt)
        return list(result.all())

    async def get_product_count_for_category(self, category_id: UUID) -> int:
        """获取分类下的商品数量"""
        stmt = select(ProductCategory).where(
            ProductCategory.category_id == category_id
        )
        result = await self.db.scalars(stmt)
        return len(list(result.all()))

    async def replace_for_product(self, product_id: UUID, category_ids: list[UUID]) -> None:
        """替换商品的分类关联（先删后建）"""
        await self.db.execute(
            delete(ProductCategory).where(ProductCategory.product_id == product_id)
        )
        for cid in category_ids:
            self.db.add(ProductCategory(product_id=product_id, category_id=cid))


class ProductSpecRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_product(self, product_id: UUID) -> list[ProductSpec]:
        stmt = (
            select(ProductSpec)
            .where(ProductSpec.product_id == product_id)
            .order_by(ProductSpec.sort_order)
        )
        result = await self.db.scalars(stmt)
        return list(result.all())

    async def replace_for_product(self, product_id: UUID, specs: list[dict]) -> list[ProductSpec]:
        """替换商品规格模板"""
        await self.db.execute(
            delete(ProductSpec).where(ProductSpec.product_id == product_id)
        )
        new_specs = []
        for s in specs:
            spec = ProductSpec(product_id=product_id, **s)
            self.db.add(spec)
            new_specs.append(spec)
        return new_specs


class ProductSkuRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_product(self, product_id: UUID) -> list[ProductSku]:
        stmt = (
            select(ProductSku)
            .where(ProductSku.product_id == product_id)
            .order_by(ProductSku.sort_order)
        )
        result = await self.db.scalars(stmt)
        return list(result.all())

    async def get_by_id(self, sku_id: UUID) -> ProductSku | None:
        return await self.db.get(ProductSku, sku_id)

    async def replace_for_product(self, product_id: UUID, skus: list[dict]) -> list[ProductSku]:
        """替换商品 SKU"""
        await self.db.execute(
            delete(ProductSku).where(ProductSku.product_id == product_id)
        )
        new_skus = []
        for s in skus:
            sku = ProductSku(product_id=product_id, **s)
            self.db.add(sku)
            new_skus.append(sku)
        return new_skus


class ProductLevelPriceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_for_product(self, product_id: UUID) -> list[ProductLevelPrice]:
        stmt = select(ProductLevelPrice).where(
            ProductLevelPrice.product_id == product_id
        )
        result = await self.db.scalars(stmt)
        return list(result.all())

    async def find_exact(
        self, product_id: UUID, sku_id: UUID | None, level_id: UUID
    ) -> ProductLevelPrice | None:
        """精确查找等级价（SKU 级或商品级）"""
        stmt = select(ProductLevelPrice).where(
            ProductLevelPrice.product_id == product_id,
            ProductLevelPrice.level_id == level_id,
        )
        if sku_id is not None:
            stmt = stmt.where(ProductLevelPrice.sku_id == sku_id)
        else:
            stmt = stmt.where(ProductLevelPrice.sku_id.is_(None))
        return await self.db.scalar(stmt)

    async def replace_for_product(self, product_id: UUID, items: list[dict]) -> None:
        """替换商品等级价"""
        await self.db.execute(
            delete(ProductLevelPrice).where(
                ProductLevelPrice.product_id == product_id
            )
        )
        for item in items:
            self.db.add(ProductLevelPrice(product_id=product_id, **item))


class ProductLevelCommissionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_for_product(self, product_id: UUID) -> list[ProductLevelCommission]:
        stmt = select(ProductLevelCommission).where(
            ProductLevelCommission.product_id == product_id
        )
        result = await self.db.scalars(stmt)
        return list(result.all())

    async def find_for_product_and_level(
        self, product_id: UUID, level_id: UUID
    ) -> ProductLevelCommission | None:
        stmt = select(ProductLevelCommission).where(
            ProductLevelCommission.product_id == product_id,
            ProductLevelCommission.level_id == level_id,
        )
        return await self.db.scalar(stmt)

    async def replace_for_product(self, product_id: UUID, items: list[dict]) -> None:
        """替换商品独立分佣"""
        await self.db.execute(
            delete(ProductLevelCommission).where(
                ProductLevelCommission.product_id == product_id
            )
        )
        for item in items:
            self.db.add(ProductLevelCommission(product_id=product_id, **item))
