"""
File: app/domains/carts/constants.py
Description: 购物车常量与错误码

Author: jinmozhe
Created: 2026-04-12
"""

from app.core.exceptions import BaseErrorCode

class CartError(BaseErrorCode):
    """购物车领域错误码"""
    MISSING_IDENTITY = (400, "cart.missing_identity", "缺少用户身份或设备信息，无法操作购物车")
    CART_ITEM_NOT_FOUND = (404, "cart.not_found", "购物车不存在此项或无权操作")
    INVALID_QUANTITY = (400, "cart.invalid_quantity", "商品数量必须大于 0")
    PRODUCT_ERROR = (400, "cart.product_error", "商品异常或已被删除")
    STOCK_INSUFFICIENT = (400, "cart.stock_insufficient", "商品库存不足")
