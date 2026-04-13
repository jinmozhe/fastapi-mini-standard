"""
File: app/domains/orders/constants.py
Description: 订单领域常量与错误码

Author: jinmozhe
Created: 2026-04-13
"""

from enum import StrEnum

from app.core.exceptions import BaseErrorCode


class OrderStatus(StrEnum):
    """订单状态"""
    PENDING_PAYMENT = "pending_payment"      # 待付款
    PENDING_SHIPMENT = "pending_shipment"    # 待发货
    SHIPPED = "shipped"                      # 已发货
    COMPLETED = "completed"                  # 已完成
    CANCELLED = "cancelled"                  # 已取消


class CommissionStatus(StrEnum):
    """佣金状态"""
    FROZEN = "frozen"      # 已冻结
    SETTLED = "settled"    # 已结算
    REVOKED = "revoked"    # 已撤销


class CommissionLevel(StrEnum):
    """佣金层级"""
    FIRST = "first"    # 直推
    SECOND = "second"  # 间推
    OTHER = "other"    # 其它


class OrderError(BaseErrorCode):
    """订单领域错误码"""
    NOT_FOUND = (404, "order.not_found", "订单不存在")
    CART_EMPTY = (400, "order.cart_empty", "请选择要结算的商品")
    PRODUCT_UNAVAILABLE = (400, "order.product_unavailable", "部分商品已下架或不可购买")
    STOCK_INSUFFICIENT = (400, "order.stock_insufficient", "库存不足，请减少购买数量")
    INVALID_STATUS = (400, "order.invalid_status", "当前订单状态不允许此操作")
    ALREADY_PAID = (400, "order.already_paid", "该订单已完成支付")
    CANNOT_CANCEL = (400, "order.cannot_cancel", "已支付的订单不可自助取消，请联系客服")
    ADDRESS_REQUIRED = (400, "order.address_required", "请选择收货地址")
