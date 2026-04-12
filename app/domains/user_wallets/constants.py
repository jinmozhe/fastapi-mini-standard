"""
File: app/domains/user_wallets/constants.py
Description: 用户钱包领域相关的常量、枚举与错误码定义

Author: jinmozhe
Created: 2026-04-12
"""

from enum import StrEnum

from app.core.error_code import BaseErrorCode


class BalanceChangeType(StrEnum):
    """资金变动类型 —— 每个值对应一段确定的业务代码路径"""

    # ---- 入账类 (+) ----
    ORDER_REFUND = "order_refund"  # 订单退款返还
    COMMISSION_FIRST = "commission_first"  # 直推佣金到账
    COMMISSION_SECOND = "commission_second"  # 间推佣金到账
    COMMISSION_OTHER = "commission_other"  # 额外佣金到账
    UPGRADE_REWARD = "upgrade_reward"  # 下级升级奖励到账
    ADMIN_RECHARGE = "admin_recharge"  # 后台手工充值（客诉补偿等）

    # ---- 扣减类 (-) ----
    ORDER_PAY = "order_pay"  # 余额支付扣款
    WITHDRAW_APPLY = "withdraw_apply"  # 提现申请冻结
    WITHDRAW_SUCCESS = "withdraw_success"  # 提现成功扣减冻结
    WITHDRAW_REJECT = "withdraw_reject"  # 提现驳回解冻
    ADMIN_DEDUCT = "admin_deduct"  # 后台手工扣款


class PointChangeType(StrEnum):
    """积分变动类型"""

    # ---- 获取类 (+) ----
    ORDER_COMPLETE = "order_complete"  # 订单完成赠送积分
    SIGN_IN = "sign_in"  # 每日签到
    INVITE_REGISTER = "invite_register"  # 邀请新用户注册奖励
    ADMIN_GRANT = "admin_grant"  # 后台手工发放

    # ---- 消耗类 (-) ----
    ORDER_DEDUCT = "order_deduct"  # 积分抵扣订单金额
    EXCHANGE_GOODS = "exchange_goods"  # 积分兑换商品
    ORDER_REFUND_REVOKE = "order_refund_revoke"  # 退款撤回已赠积分
    POINTS_EXPIRE = "points_expire"  # 积分过期清零
    ADMIN_REVOKE = "admin_revoke"  # 后台手工扣除


class WalletError(BaseErrorCode):
    """
    钱包相关的业务错误码
    """

    WALLET_NOT_FOUND = "wallet.not_found"
    INSUFFICIENT_BALANCE = "wallet.insufficient_balance"
    INSUFFICIENT_POINTS = "wallet.insufficient_points"
    CONCURRENT_UPDATE_FAILED = "wallet.concurrent_update_failed"
    INVALID_AMOUNT = "wallet.invalid_amount"
