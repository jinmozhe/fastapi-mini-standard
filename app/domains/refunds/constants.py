"""
File: app/domains/refunds/constants.py
Description: 售后退款领域常量与错误码

Author: jinmozhe
Created: 2026-04-13
"""

from enum import StrEnum

from app.core.exceptions import BaseErrorCode


class RefundStatus(StrEnum):
    """退款状态"""
    PENDING = "pending"        # 待审核
    APPROVED = "approved"      # 已通过
    RETURNING = "returning"    # 退货中
    REFUNDED = "refunded"      # 已退款
    REJECTED = "rejected"      # 已驳回


class RefundType(StrEnum):
    """退款类型"""
    REFUND_ONLY = "refund_only"        # 仅退款
    RETURN_REFUND = "return_refund"    # 退货退款


class RefundError(BaseErrorCode):
    """售后领域错误码"""
    NOT_FOUND = (404, "refund.not_found", "退款记录不存在")
    ORDER_NOT_FOUND = (404, "refund.order_not_found", "订单不存在")
    NOT_REFUNDABLE = (400, "refund.not_refundable", "该商品不支持退款")
    ORDER_STATUS_INVALID = (400, "refund.order_status_invalid", "当前订单状态不允许申请退款")
    ALREADY_APPLIED = (400, "refund.already_applied", "该订单已有进行中的退款申请")
    INVALID_STATUS = (400, "refund.invalid_status", "当前退款状态不允许此操作")
    AMOUNT_EXCEED = (400, "refund.amount_exceed", "退款金额不能超过订单实付金额")
