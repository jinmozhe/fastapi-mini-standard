"""
File: app/domains/products/constants.py
Description: 商品领域枚举常量与错误码

Author: jinmozhe
Created: 2026-04-12
"""

from enum import StrEnum

from app.core.exceptions import BaseErrorCode


# ==============================================================================
# 商品类型
# ==============================================================================


class ProductType(StrEnum):
    """商品类型"""
    VIRTUAL = "virtual"      # 虚拟商品
    PHYSICAL = "physical"    # 实体商品


# ==============================================================================
# 商品状态
# ==============================================================================


class ProductStatus(StrEnum):
    """商品上架状态"""
    DRAFT = "draft"          # 草稿
    ON_SALE = "on_sale"      # 在售
    OFF_SALE = "off_sale"    # 下架


# ==============================================================================
# 错误码
# ==============================================================================


from starlette.status import HTTP_400_BAD_REQUEST

class ProductError(BaseErrorCode):
    """商品领域错误码"""
    # 分类相关
    CATEGORY_NOT_FOUND = (HTTP_400_BAD_REQUEST, "products.category_not_found", "分类不存在")
    CATEGORY_MAX_DEPTH = (HTTP_400_BAD_REQUEST, "products.category_max_depth", "分类层级不能超过3级")
    CATEGORY_HAS_PRODUCTS = (HTTP_400_BAD_REQUEST, "products.category_has_products", "分类下存在关联商品，无法删除")
    CATEGORY_HAS_CHILDREN = (HTTP_400_BAD_REQUEST, "products.category_has_children", "分类下存在子分类，无法删除")

    # 商品相关
    PRODUCT_NOT_FOUND = (HTTP_400_BAD_REQUEST, "products.not_found", "商品不存在")
    PRODUCT_ALREADY_ON_SALE = (HTTP_400_BAD_REQUEST, "products.already_on_sale", "商品已在售")
    PRODUCT_NO_SKU_STOCK_REQUIRED = (
        HTTP_400_BAD_REQUEST, "products.no_sku_stock_required", "无 SKU 商品必须设置库存和成本价"
    )
    INVALID_PRODUCT_TYPE = (HTTP_400_BAD_REQUEST, "products.invalid_type", "无效的商品类型")

    # SKU 相关
    SKU_NOT_FOUND = (HTTP_400_BAD_REQUEST, "products.sku_not_found", "SKU 不存在")
    SKU_CODE_DUPLICATE = (HTTP_400_BAD_REQUEST, "products.sku_code_duplicate", "SKU 编码已存在")
    SKU_INSUFFICIENT_STOCK = (HTTP_400_BAD_REQUEST, "products.sku_insufficient_stock", "库存不足")
