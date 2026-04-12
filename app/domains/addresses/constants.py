"""
File: app/domains/addresses/constants.py
Description: 收货地址常量与错误码

Author: jinmozhe
Created: 2026-04-12
"""

from app.core.exceptions import BaseErrorCode


class AddressError(BaseErrorCode):
    """收货地址领域错误码"""
    NOT_FOUND = (404, "address.not_found", "地址不存在或无权操作")
    MAX_LIMIT_REACHED = (400, "address.max_limit", "收货地址最多保存 20 个")
    CANNOT_DELETE_ONLY_ADDRESS = (400, "address.cannot_delete_only", "至少保留一个收货地址")


# 单用户最大地址容量
ADDRESS_MAX_COUNT = 20
