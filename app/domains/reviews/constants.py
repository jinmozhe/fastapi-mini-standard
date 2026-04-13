"""
File: app/domains/reviews/constants.py
Description: 评价领域常量与错误码

Author: jinmozhe
Created: 2026-04-13
"""

from app.core.exceptions import BaseErrorCode


class ReviewError(BaseErrorCode):
    """评价领域错误码"""
    NOT_FOUND = (404, "review.not_found", "评价不存在")
    ORDER_NOT_FOUND = (404, "review.order_not_found", "订单不存在")
    ORDER_NOT_COMPLETED = (400, "review.order_not_completed", "订单未完成，无法评价")
    ALREADY_REVIEWED = (400, "review.already_reviewed", "该商品已评价")
    INVALID_RATING = (400, "review.invalid_rating", "评分范围为 1-5")
    ITEM_NOT_FOUND = (400, "review.item_not_found", "订单明细不存在")
