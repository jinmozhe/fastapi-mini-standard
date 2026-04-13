"""
File: app/domains/fulfillment/constants.py
Description: 履约领域常量与错误码

Author: jinmozhe
Created: 2026-04-13
"""

from app.core.exceptions import BaseErrorCode


# 自动确认收货天数（发货后 N 天未操作自动确认）
AUTO_CONFIRM_DAYS: int = 15


class FulfillmentError(BaseErrorCode):
    """履约领域错误码"""
    ORDER_NOT_FOUND = (404, "fulfillment.order_not_found", "订单不存在")
    CANNOT_SHIP = (400, "fulfillment.cannot_ship", "当前订单状态不允许发货")
    CANNOT_CONFIRM = (400, "fulfillment.cannot_confirm", "当前订单状态不允许确认收货")
    BATCH_PARTIAL_FAIL = (400, "fulfillment.batch_partial_fail", "部分订单发货失败")
