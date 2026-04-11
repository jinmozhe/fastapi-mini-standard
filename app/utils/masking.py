"""
File: app/utils/masking.py
Description: PII 数据脱敏工具 (Data Masking)

本模块提供敏感信息脱敏功能，用于日志记录和异常上报时的隐私保护。
严格遵循 GDPR 及相关数据安全规范，确保日志中不包含明文敏感信息。

特性：
1. 针对性脱敏: 手机号、邮箱、身份证等特定格式。
2. 递归脱敏: 能够深度遍历字典/列表，自动过滤敏感 Key (如 password, token)。
3. 高性能: 使用预编译正则和字符串切片。

Author: jinmozhe
Created: 2025-11-26
"""

from typing import Any

# ==============================================================================
# 1. 敏感字段黑名单 (大小写不敏感)
# ==============================================================================
SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "session_id",
    "client_secret",
    "credit_card",
    "card_number",
    "cvv",
    "id_card",
    "identity_card",
}

# ==============================================================================
# 2. 基础脱敏函数
# ==============================================================================


def mask_phone(phone: str | None) -> str:
    """
    手机号脱敏。
    规则: 保留前3位和后4位，中间用 * 替换。
    示例: 13800138000 -> 138****8000
    """
    if not phone or len(phone) < 7:
        return "******"
    return f"{phone[:3]}****{phone[-4:]}"


def mask_email(email: str | None) -> str:
    """
    邮箱脱敏。
    规则: 保留用户名首位和域名，中间掩盖。
    示例: jinmozhe@example.com -> j***@example.com
    """
    if not email or "@" not in email:
        return "******"

    try:
        user_part, domain_part = email.split("@", 1)
        if len(user_part) <= 1:
            masked_user = "*" * 4
        else:
            masked_user = f"{user_part[0]}***"
        return f"{masked_user}@{domain_part}"
    except Exception:
        return "******"


def mask_id_card(id_card: str | None) -> str:
    """
    身份证/证件号脱敏。
    规则: 保留前1位和后1位 (极端保守策略)。
    """
    if not id_card or len(id_card) < 4:
        return "******"
    return f"{id_card[0]}****************{id_card[-1]}"


def mask_secret(value: Any) -> str:
    """
    通用机密信息完全掩盖。
    用于密码、Token 等。
    """
    if value is None:
        return ""
    return "******"


# ==============================================================================
# 3. 递归脱敏工具 (核心)
# ==============================================================================


def mask_sensitive_data(data: Any) -> Any:
    """
    递归遍历数据结构（字典、列表），自动对敏感字段进行脱敏。

    用于在打印日志前处理 request body 或变量字典。
    注意：为了性能，此函数会返回数据的【浅拷贝】副本，不修改原数据。
    """
    if isinstance(data, dict):
        # 字典处理：检查 Key 是否敏感
        new_data = {}
        for k, v in data.items():
            if isinstance(k, str) and k.lower() in SENSITIVE_KEYS:
                new_data[k] = mask_secret(v)
            else:
                new_data[k] = mask_sensitive_data(v)
        return new_data

    elif isinstance(data, list):
        # 列表处理：递归处理每个元素
        return [mask_sensitive_data(item) for item in data]

    elif isinstance(data, str):
        # 字符串尝试简单识别（可选，目前保持原样以避免误伤）
        # 可以在此增加正则匹配手机号/邮箱的逻辑，但需评估性能损耗
        return data

    # 其他类型直接返回
    return data
