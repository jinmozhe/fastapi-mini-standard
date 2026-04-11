"""
File: app/domains/admin/constants.py
Description: B端管理员领域常量定义 (错误码 + 成功提示)
Namespace: admin.*

Author: jinmozhe
Created: 2026-04-12
"""

from starlette.status import (
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

from app.core.error_code import BaseErrorCode


class AdminError(BaseErrorCode):
    """
    B端管理员领域错误码定义
    Tuple Structure: (HTTP_Status, Code_String, Default_Message)
    """

    # 账号不存在 (用于查询场景，非登录)
    ADMIN_NOT_FOUND = (HTTP_404_NOT_FOUND, "admin.not_found", "管理员账号不存在")

    # 用户名冲突
    USERNAME_EXIST = (HTTP_409_CONFLICT, "admin.username_exist", "该用户名已被占用")

    # 登录凭证错误 (安全掩码，不区分用户名/密码)
    INVALID_CREDENTIALS = (
        HTTP_403_FORBIDDEN,
        "admin.invalid_credentials",
        "账号或密码错误",
    )

    # 账号状态异常
    ACCOUNT_DISABLED = (HTTP_403_FORBIDDEN, "admin.account_disabled", "该管理员账号已被停用")

    # 权限不足 (缺少特定操作权限码)
    PERMISSION_DENIED = (
        HTTP_403_FORBIDDEN,
        "admin.permission_denied",
        "权限不足，您无法执行该操作",
    )

    # B 端 Token 盗用检测
    TOKEN_THEFT_DETECTED = (
        HTTP_401_UNAUTHORIZED,
        "admin.token_theft_detected",
        "安全警告：检测到会话异常，该管理员会话已被强制注销，请重新登录。",
    )


class AdminMsg:
    """
    B端管理员领域成功提示文案
    """

    LOGIN_SUCCESS = "管理员登录成功"
    LOGOUT_SUCCESS = "已安全退出后台"
    REFRESH_SUCCESS = "令牌刷新成功"
    ME_SUCCESS = "获取管理员信息成功"
