"""
File: app/domains/withdrawals/constants.py
Description: 提现领域常量与错误码

Author: jinmozhe
Created: 2026-04-13
"""

from decimal import Decimal
from enum import StrEnum

from app.core.exceptions import BaseErrorCode

# 最低提现金额
MIN_WITHDRAW_AMOUNT = Decimal("10.00")

# 手续费率（0 = 免手续费）
WITHDRAW_FEE_RATE = Decimal("0.00")


class WithdrawalStatus(StrEnum):
    """提现状态"""
    PENDING = "pending"        # 待审核
    APPROVED = "approved"      # 已通过（打款中）
    COMPLETED = "completed"    # 已完成
    REJECTED = "rejected"      # 已驳回


class WithdrawalChannel(StrEnum):
    """提现通道"""
    WECHAT = "balance_to_wechat"    # 微信零钱
    BANK = "balance_to_bank"        # 银行卡
    ALIPAY = "balance_to_alipay"    # 支付宝


class WithdrawalError(BaseErrorCode):
    """提现领域错误码"""
    NOT_FOUND = (404, "withdrawal.not_found", "提现记录不存在")
    INSUFFICIENT_BALANCE = (400, "withdrawal.insufficient_balance", "可用余额不足")
    BELOW_MIN_AMOUNT = (400, "withdrawal.below_min_amount", f"提现金额不能低于 {MIN_WITHDRAW_AMOUNT} 元")
    INVALID_STATUS = (400, "withdrawal.invalid_status", "当前提现状态不允许此操作")
    PENDING_EXISTS = (400, "withdrawal.pending_exists", "您有正在审核中的提现申请，请等待处理")
    INVALID_CHANNEL = (400, "withdrawal.invalid_channel", "不支持的提现通道")
