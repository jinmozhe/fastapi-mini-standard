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
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
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

    # 验证码相关
    CAPTCHA_ERROR = (HTTP_403_FORBIDDEN, "auth.captcha_error", "验证码错误或已过期")


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
