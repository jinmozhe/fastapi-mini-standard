"""
File: app/domains/auth/constants.py
Description: 认证领域常量定义 (错误码 + 成功提示)
Namespace: auth.*

遵循 v2.1 架构规范:
1. Error 定义: 继承 BaseErrorCode，包含 (HTTP状态, 业务码, 默认文案)
2. Msg 定义: 纯字符串常量，用于 Router 返回成功响应

Author: jinmozhe
Created: 2026-01-15
"""

from starlette.status import (
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_502_BAD_GATEWAY,
)

from app.core.error_code import BaseErrorCode

# ==============================================================================
# 1. 错误码定义 (Error Codes)
# 用于 Service 层抛出异常: raise AppException(AuthError.USER_NOT_FOUND)
# ==============================================================================


class AuthError(BaseErrorCode):
    """
    认证领域错误定义
    Tuple Structure: (HTTP_Status, Code_String, Default_Message)
    """

    # HTTP 404: 资源不存在
    # 通常用于管理接口查询特定用户
    USER_NOT_FOUND = (HTTP_404_NOT_FOUND, "auth.user_not_found", "用户不存在")

    # HTTP 409: 资源冲突 (唯一性校验失败)
    PHONE_EXIST = (HTTP_409_CONFLICT, "auth.phone_exist", "该手机号已被注册")
    EMAIL_EXIST = (HTTP_409_CONFLICT, "auth.email_exist", "该邮箱已被注册")
    USERNAME_EXIST = (HTTP_409_CONFLICT, "auth.username_exist", "该用户名已被占用")

    # HTTP 403: 业务逻辑拒绝 (权限/状态/凭证错误)

    # [新增] 专门用于登录失败的通用错误 (安全掩码)
    # 替代原先的 PASSWORD_ERROR 用于登录场景，防止枚举攻击
    INVALID_CREDENTIALS = (
        HTTP_403_FORBIDDEN,
        "auth.invalid_credentials",
        "账号或密码错误",
    )

    # 具体错误，用于修改密码等场景 (如验证旧密码)
    PASSWORD_ERROR = (HTTP_403_FORBIDDEN, "auth.password_error", "密码错误")

    # 账号状态异常
    ACCOUNT_LOCKED = (HTTP_403_FORBIDDEN, "auth.account_locked", "账户已被冻结")

    CAPTCHA_ERROR = (HTTP_403_FORBIDDEN, "auth.captcha_error", "验证码错误或已过期")

    # 令牌盗用/会话家族安全异常
    TOKEN_THEFT_DETECTED = (
        HTTP_401_UNAUTHORIZED,
        "auth.token_theft_detected",
        "安全警告：检测到异地会话异常或令牌盗用，为保护您的账户，该设备及相关会话已被强制下线，请重新登录。",
    )

    # ---------- 短信验证码相关 ----------
    SMS_SEND_TOO_FREQUENT = (
        HTTP_429_TOO_MANY_REQUESTS,
        "auth.sms_send_too_frequent",
        "发送过于频繁，请稍后再试",
    )
    SMS_CODE_INVALID = (
        HTTP_403_FORBIDDEN,
        "auth.sms_code_invalid",
        "验证码错误或已过期",
    )
    SMS_SEND_FAILED = (
        HTTP_502_BAD_GATEWAY,
        "auth.sms_send_failed",
        "短信发送失败，请稍后重试",
    )

    # ---------- 微信授权相关 ----------
    WECHAT_AUTH_FAILED = (
        HTTP_502_BAD_GATEWAY,
        "auth.wechat_auth_failed",
        "微信授权失败，请重试",
    )
    WECHAT_DECRYPT_FAILED = (
        HTTP_403_FORBIDDEN,
        "auth.wechat_decrypt_failed",
        "手机号解密失败，请重新授权",
    )

    # ---------- 密码未设置 ----------
    PASSWORD_NOT_SET = (
        HTTP_403_FORBIDDEN,
        "auth.password_not_set",
        "您尚未设置密码，请使用短信验证码或微信登录",
    )

    # ---------- 社交绑定相关 ----------
    WECHAT_ALREADY_BOUND = (
        HTTP_409_CONFLICT,
        "auth.wechat_already_bound",
        "该微信已绑定其他账号",
    )
    WECHAT_NOT_BOUND = (
        HTTP_404_NOT_FOUND,
        "auth.wechat_not_bound",
        "未找到微信绑定记录",
    )
    TEMP_TOKEN_INVALID = (
        HTTP_403_FORBIDDEN,
        "auth.temp_token_invalid",
        "临时凭证无效或已过期，请重新扫码",
    )
    PHONE_ALREADY_BOUND = (
        HTTP_409_CONFLICT,
        "auth.phone_already_bound",
        "该手机号已绑定其他账号",
    )
    ACCOUNT_DELETED = (
        HTTP_403_FORBIDDEN,
        "auth.account_deleted",
        "该手机号关联的账号已被注销，如需恢复请联系客服",
    )
    UNBIND_LAST_METHOD = (
        HTTP_403_FORBIDDEN,
        "auth.unbind_last_method",
        "无法解绑：这是您唯一的登录方式，请先设置密码或绑定其他账号",
    )


# ==============================================================================
# 2. 成功提示语 (Success Messages)
# 用于 Router 层返回响应: return ResponseModel.success(message=AuthMsg.LOGIN_SUCCESS)
# ==============================================================================


class AuthMsg:
    """
    认证领域成功提示文案
    """

    LOGIN_SUCCESS = "登录成功"
    REGISTER_SUCCESS = "注册成功"
    LOGOUT_SUCCESS = "已安全退出"
    REFRESH_SUCCESS = "令牌刷新成功"
    PWD_RESET_SUCCESS = "密码重置成功"
    SMS_SEND_SUCCESS = "验证码已发送"
    SMS_LOGIN_SUCCESS = "登录成功"
    WECHAT_LOGIN_SUCCESS = "微信登录成功"
    WECHAT_BIND_SUCCESS = "微信绑定成功"
    WECHAT_UNBIND_SUCCESS = "微信解绑成功"
    WECHAT_SCAN_NEW_USER = "请绑定手机号完成注册"
    WECHAT_COMPLETE_SUCCESS = "注册完成"
    SET_PASSWORD_SUCCESS = "密码设置成功"
