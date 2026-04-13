"""
File: app/domains/referrals/constants.py
Description: 推荐关系领域常量与错误码

Author: jinmozhe
Created: 2026-04-13
"""

from app.core.exceptions import BaseErrorCode

# 邀请码长度
INVITE_CODE_LENGTH = 6


class ReferralError(BaseErrorCode):
    """推荐关系领域错误码"""
    INVITE_CODE_INVALID = (400, "referral.invite_code_invalid", "邀请码无效或不存在")
    ALREADY_BOUND = (400, "referral.already_bound", "该用户已绑定推荐人，无法重复绑定")
    SELF_INVITE = (400, "referral.self_invite", "不能邀请自己")
    CIRCULAR_BIND = (400, "referral.circular_bind", "不能形成循环推荐关系")
    PROFILE_NOT_FOUND = (404, "referral.profile_not_found", "用户等级档案不存在")
    USER_NOT_FOUND = (404, "referral.user_not_found", "用户不存在")
