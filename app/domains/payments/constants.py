"""
File: app/domains/payments/constants.py
Description: 支付领域常量与错误码

Author: jinmozhe
Created: 2026-04-13
"""

from enum import StrEnum

from app.core.exceptions import BaseErrorCode


class PaymentMethod(StrEnum):
    """支付方式"""
    WECHAT = "wechat"    # 微信支付
    BALANCE = "balance"  # 余额支付


class PaymentStatus(StrEnum):
    """支付状态"""
    PENDING = "pending"        # 待支付（微信支付已发起，等待回调）
    PAID = "paid"              # 已支付
    CLOSED = "closed"          # 已关闭（超时/取消）
    REFUNDING = "refunding"    # 退款中
    REFUNDED = "refunded"      # 已退款


VALID_PAYMENT_METHODS = {PaymentMethod.WECHAT, PaymentMethod.BALANCE}


class PaymentError(BaseErrorCode):
    """支付领域错误码"""
    NOT_FOUND = (404, "payment.not_found", "支付记录不存在")
    ALREADY_PAID = (400, "payment.already_paid", "该订单已完成支付")
    INVALID_METHOD = (400, "payment.invalid_method", "不支持的支付方式")
    INSUFFICIENT_BALANCE = (400, "payment.insufficient_balance", "余额不足，请选择微信支付")
    WECHAT_PAY_DISABLED = (503, "payment.wechat_disabled", "微信支付服务暂未开启")
    WECHAT_PAY_FAILED = (502, "payment.wechat_failed", "微信支付下单失败，请稍后重试")
    CALLBACK_VERIFY_FAILED = (400, "payment.callback_verify_failed", "支付回调签名校验失败")
    INVALID_STATUS = (400, "payment.invalid_status", "当前支付状态不允许此操作")
    REFUND_AMOUNT_EXCEEDED = (400, "payment.refund_exceeded", "退款金额超过已支付金额")
