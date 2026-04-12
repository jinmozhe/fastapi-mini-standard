"""
File: app/domains/products/service.py
Description: 商品领域核心业务逻辑

包含：
- 分类 CRUD + 3 级限制校验
- 商品 CRUD + 状态管理
- 规格模板 & SKU 批量管理
- 5 级价格优先级引擎
- 3 级分佣优先级引擎

Author: jinmozhe
Created: 2026-04-12
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.logging import logger
from app.db.models.product import (
    Category,
    Product,
    ProductLevelCommission,
    ProductLevelPrice,
)
from app.domains.products.constants import ProductError, ProductStatus
from app.domains.products.repository import (
    CategoryRepository,
    ProductCategoryRepository,
    ProductLevelCommissionRepository,
    ProductLevelPriceRepository,
    ProductRepository,
    ProductSkuRepository,
    ProductSpecRepository,
)


class ProductService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.category_repo = CategoryRepository(db)
        self.product_repo = ProductRepository(db)
        self.pc_repo = ProductCategoryRepository(db)
        self.spec_repo = ProductSpecRepository(db)
        self.sku_repo = ProductSkuRepository(db)
        self.level_price_repo = ProductLevelPriceRepository(db)
        self.level_commission_repo = ProductLevelCommissionRepository(db)

    # ==========================================================================
    # 分类管理
    # ==========================================================================

    async def create_category(self, data: dict) -> Category:
        """创建分类，校验不超过 3 级"""
        parent_id = data.get("parent_id")
        if parent_id:
            # 校验父分类存在
            parent = await self.category_repo.get_by_id(parent_id)
            if not parent:
                raise AppException(ProductError.CATEGORY_NOT_FOUND)
            # 校验深度：父分类的深度 + 1 不超过 3
            parent_depth = await self.category_repo.get_depth(parent_id)
            if parent_depth >= 3:
                raise AppException(ProductError.CATEGORY_MAX_DEPTH)

        # 序列化 JSONB 规则
        level_prices = data.pop("level_prices", None)
        level_commissions = data.pop("level_commissions", None)

        category = Category(**data)
        if level_prices is not None:
            category.level_prices = [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in level_prices]
        if level_commissions is not None:
            category.level_commissions = [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in level_commissions]

        self.db.add(category)
        await self.db.flush()
        logger.info("category_created", id=str(category.id), name=category.name)
        return category

    async def update_category(self, category_id: UUID, data: dict) -> Category:
        """更新分类"""
        category = await self.category_repo.get_by_id(category_id)
        if not category:
            raise AppException(ProductError.CATEGORY_NOT_FOUND)

        # 如果修改 parent_id，需要重新校验深度
        new_parent_id = data.get("parent_id")
        if new_parent_id is not None and new_parent_id != category.parent_id:
            if new_parent_id:
                parent_depth = await self.category_repo.get_depth(new_parent_id)
                if parent_depth >= 3:
                    raise AppException(ProductError.CATEGORY_MAX_DEPTH)

        # 处理 JSONB 规则字段
        level_prices = data.pop("level_prices", None)
        level_commissions = data.pop("level_commissions", None)

        for key, value in data.items():
            if value is not None:
                setattr(category, key, value)

        if level_prices is not None:
            category.level_prices = [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in level_prices]
        if level_commissions is not None:
            category.level_commissions = [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in level_commissions]

        await self.db.flush()
        return category

    async def delete_category(self, category_id: UUID) -> None:
        """删除分类（有子分类或商品关联时拒绝）"""
        category = await self.category_repo.get_by_id(category_id)
        if not category:
            raise AppException(ProductError.CATEGORY_NOT_FOUND)

        # 检查子分类
        children_count = await self.category_repo.get_children_count(category_id)
        if children_count > 0:
            raise AppException(ProductError.CATEGORY_HAS_CHILDREN)

        # 检查商品关联
        product_count = await self.pc_repo.get_product_count_for_category(category_id)
        if product_count > 0:
            raise AppException(ProductError.CATEGORY_HAS_PRODUCTS)

        await self.db.delete(category)
        await self.db.flush()
        logger.info("category_deleted", id=str(category_id))

    async def get_category_tree(self, active_only: bool = True) -> list[dict]:
        """获取分类树形结构"""
        categories = (
            await self.category_repo.get_all_active()
            if active_only
            else await self.category_repo.get_all()
        )

        # 构建树
        cat_map: dict[UUID, dict] = {}
        for cat in categories:
            cat_map[cat.id] = {
                "category": cat,
                "children": [],
            }

        roots = []
        for cat in categories:
            node = cat_map[cat.id]
            if cat.parent_id and cat.parent_id in cat_map:
                cat_map[cat.parent_id]["children"].append(node)
            else:
                roots.append(node)

        return roots

    # ==========================================================================
    # 商品 CRUD
    # ==========================================================================

    async def create_product(self, data: dict) -> Product:
        """创建商品"""
        category_ids = data.pop("category_ids", None)

        product = Product(**data)
        self.db.add(product)
        await self.db.flush()

        # 关联分类
        if category_ids:
            await self.pc_repo.replace_for_product(product.id, category_ids)
            await self.db.flush()

        logger.info("product_created", id=str(product.id), name=product.name)
        return product

    async def update_product(self, product_id: UUID, data: dict) -> Product:
        """更新商品基本信息"""
        product = await self.product_repo.get_by_id(product_id)
        if not product or product.is_deleted:
            raise AppException(ProductError.PRODUCT_NOT_FOUND)

        for key, value in data.items():
            if value is not None:
                setattr(product, key, value)

        await self.db.flush()
        return product

    async def update_product_status(self, product_id: UUID, status: str) -> Product:
        """更新商品状态"""
        product = await self.product_repo.get_by_id(product_id)
        if not product or product.is_deleted:
            raise AppException(ProductError.PRODUCT_NOT_FOUND)

        product.status = status
        await self.db.flush()
        logger.info("product_status_changed", id=str(product_id), status=status)
        return product

    async def soft_delete_product(self, product_id: UUID) -> None:
        """软删除商品"""
        product = await self.product_repo.get_by_id(product_id)
        if not product:
            raise AppException(ProductError.PRODUCT_NOT_FOUND)

        from datetime import UTC, datetime

        product.is_deleted = True
        product.deleted_at = datetime.now(UTC)
        await self.db.flush()
        logger.info("product_soft_deleted", id=str(product_id))

    async def get_product_detail(self, product_id: UUID) -> dict:
        """获取商品详情（含 SKU、规格、分类等）"""
        product = await self.product_repo.get_by_id(product_id)
        if not product or product.is_deleted:
            raise AppException(ProductError.PRODUCT_NOT_FOUND)

        categories = await self.pc_repo.get_categories_for_product(product_id)
        specs = await self.spec_repo.get_by_product(product_id)
        skus = await self.sku_repo.get_by_product(product_id)

        return {
            "product": product,
            "categories": categories,
            "specs": specs,
            "skus": skus,
        }

    # ==========================================================================
    # 规格 & SKU 批量管理
    # ==========================================================================

    async def replace_specs(self, product_id: UUID, specs: list[dict]) -> list:
        """批量替换规格模板"""
        product = await self.product_repo.get_by_id(product_id)
        if not product or product.is_deleted:
            raise AppException(ProductError.PRODUCT_NOT_FOUND)

        result = await self.spec_repo.replace_for_product(product_id, specs)
        await self.db.flush()
        return result

    async def replace_skus(self, product_id: UUID, skus: list[dict]) -> list:
        """批量替换 SKU"""
        product = await self.product_repo.get_by_id(product_id)
        if not product or product.is_deleted:
            raise AppException(ProductError.PRODUCT_NOT_FOUND)

        # 替换 SKU 前先清理关联的等级价（防止外键断裂）
        await self.level_price_repo.replace_for_product(product_id, [])
        result = await self.sku_repo.replace_for_product(product_id, skus)
        await self.db.flush()
        return result

    async def replace_categories(self, product_id: UUID, category_ids: list[UUID]) -> None:
        """批量替换商品所属分类"""
        product = await self.product_repo.get_by_id(product_id)
        if not product or product.is_deleted:
            raise AppException(ProductError.PRODUCT_NOT_FOUND)

        await self.pc_repo.replace_for_product(product_id, category_ids)
        await self.db.flush()

    async def replace_level_prices(self, product_id: UUID, items: list[dict]) -> None:
        """批量替换等级价"""
        product = await self.product_repo.get_by_id(product_id)
        if not product or product.is_deleted:
            raise AppException(ProductError.PRODUCT_NOT_FOUND)

        await self.level_price_repo.replace_for_product(product_id, items)
        await self.db.flush()

    async def replace_level_commissions(self, product_id: UUID, items: list[dict]) -> None:
        """批量替换独立分佣"""
        product = await self.product_repo.get_by_id(product_id)
        if not product or product.is_deleted:
            raise AppException(ProductError.PRODUCT_NOT_FOUND)

        await self.level_commission_repo.replace_for_product(product_id, items)
        await self.db.flush()

    # ==========================================================================
    # 5 级价格引擎
    # ==========================================================================

    async def get_display_price(
        self,
        product: Product,
        sku_id: UUID | None,
        user_level_id: UUID | None,
        user_level_discount_rate: Decimal | None = None,
    ) -> tuple[Decimal, str | None]:
        """
        5 级价格优先级引擎

        返回: (最终价格, 会员价标签 or None)
        """
        # 基础售价
        if sku_id:
            sku = await self.sku_repo.get_by_id(sku_id)
            base = sku.price if sku else product.base_price
        else:
            base = product.base_price

        if not user_level_id:
            # 未登录 / 无等级 → 原价
            return base, None

        # 优先级 1：SKU 级固定价
        if sku_id:
            exact = await self.level_price_repo.find_exact(product.id, sku_id, user_level_id)
            if exact:
                return exact.price, "会员专属价"

        # 优先级 2：商品级固定价
        product_level = await self.level_price_repo.find_exact(product.id, None, user_level_id)
        if product_level:
            return product_level.price, "会员专属价"

        # 优先级 3：分类级折扣率（多分类取最优惠）
        categories = await self.pc_repo.get_categories_for_product(product.id)
        best_category_price: Decimal | None = None
        for cat in categories:
            if cat.level_prices:
                for rule in cat.level_prices:
                    if rule.get("level_id") == str(user_level_id):
                        rate = Decimal(str(rule["discount_rate"]))
                        cat_price = (base * rate).quantize(Decimal("0.01"))
                        if best_category_price is None or cat_price < best_category_price:
                            best_category_price = cat_price

        if best_category_price is not None:
            return best_category_price, "分类优惠价"

        # 优先级 4：等级通用折扣率
        if user_level_discount_rate and user_level_discount_rate < Decimal("1.0"):
            discounted = (base * user_level_discount_rate).quantize(Decimal("0.01"))
            return discounted, "会员折扣价"

        # 优先级 5：原价
        return base, None

    # ==========================================================================
    # 3 级分佣引擎
    # ==========================================================================

    async def get_commission_for_product(
        self,
        product_id: UUID,
        referrer_level_id: UUID,
        paid_amount: Decimal,
    ) -> tuple[Decimal, Decimal, Decimal]:
        """
        3 级分佣优先级引擎

        返回: (直推佣金, 间推佣金, 其它佣金)
        """
        # 优先级 1：商品级固定金额
        plc = await self.level_commission_repo.find_for_product_and_level(
            product_id, referrer_level_id
        )
        if plc:
            return plc.commission_first, plc.commission_second, plc.commission_other

        # 优先级 2：分类级百分比分佣（多分类取最高）
        categories = await self.pc_repo.get_categories_for_product(product_id)
        best_first = Decimal("0")
        best_second = Decimal("0")
        best_other = Decimal("0")
        found_category_rule = False

        for cat in categories:
            if cat.level_commissions:
                for rule in cat.level_commissions:
                    if rule.get("level_id") == str(referrer_level_id):
                        found_category_rule = True
                        first = (paid_amount * Decimal(str(rule.get("first_rate", 0)))).quantize(Decimal("0.01"))
                        second = (paid_amount * Decimal(str(rule.get("second_rate", 0)))).quantize(Decimal("0.01"))
                        other = (paid_amount * Decimal(str(rule.get("other_rate", 0)))).quantize(Decimal("0.01"))
                        # 取总佣金最高的分类
                        if (first + second + other) > (best_first + best_second + best_other):
                            best_first, best_second, best_other = first, second, other

        if found_category_rule:
            return best_first, best_second, best_other

        # 优先级 3：等级通用分佣规则 → 由 OrderService 在调用端处理
        # 这里返回全零表示"本商品无独立分佣，请回退等级通用规则"
        return Decimal("0"), Decimal("0"), Decimal("0")
