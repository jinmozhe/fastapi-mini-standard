"""
File: app/domains/shipping/constants.py
Description: 运费模板领域常量与错误码

Author: jinmozhe
Created: 2026-04-13
"""

from app.core.exceptions import BaseErrorCode


class ShippingError(BaseErrorCode):
    """运费模板领域错误码"""
    TEMPLATE_NOT_FOUND = (404, "shipping.template_not_found", "运费模板不存在")
    TEMPLATE_IN_USE = (400, "shipping.template_in_use", "该模板仍被商品引用，无法删除")
    MISSING_DEFAULT_REGION = (400, "shipping.missing_default_region", "必须包含一条「其余地区」兜底规则（province_codes 为空数组）")
    INVALID_PRICING_METHOD = (400, "shipping.invalid_pricing_method", "计价方式仅支持 weight 或 piece")
    DUPLICATE_PROVINCE_CODE = (400, "shipping.duplicate_province_code", "地区规则中存在重复的省份编码")


# 允许的计价方式
VALID_PRICING_METHODS = {"weight", "piece"}

# 快递公司常量（用于发货填写，非运费计算）
SHIPPING_COMPANIES = {
    "shunfeng": "顺丰速运",
    "yuantong": "圆通快递",
    "zhongtong": "中通快递",
    "yunda": "韵达快递",
    "shentong": "申通快递",
    "jitu": "极兔速递",
    "ems": "邮政/EMS",
}
