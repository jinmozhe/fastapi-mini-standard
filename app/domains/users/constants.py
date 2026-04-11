"""
File: app/domains/users/constants.py
Description: 用户领域常量定义（错误码 + 成功提示）

Author: jinmozhe
Created: 2026-04-03
"""

from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

from app.core.error_code import BaseErrorCode


class UserError(BaseErrorCode):
    """
    用户领域错误码
    Tuple Structure: (HTTP_Status, Code_String, Default_Message)
    """

    NOT_FOUND = (HTTP_404_NOT_FOUND, "user.not_found", "用户不存在")
    PHONE_EXIST = (HTTP_409_CONFLICT, "user.phone_exist", "该手机号已被其他用户注册")
    EMAIL_EXIST = (HTTP_409_CONFLICT, "user.email_exist", "该邮箱已被其他用户注册")
    USERNAME_EXIST = (HTTP_409_CONFLICT, "user.username_exist", "该用户名已被其他用户占用")
    INVALID_PASSWORD = (HTTP_400_BAD_REQUEST, "user.invalid_password", "密码格式不正确")


class UserMsg:
    """
    用户领域成功提示文案
    """

    UPDATE_SUCCESS = "用户资料更新成功"
    DELETE_SUCCESS = "账户已注销"
