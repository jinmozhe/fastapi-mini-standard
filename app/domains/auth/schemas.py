"""
File: app/domains/auth/schemas.py
Description: 认证领域 Pydantic 模型 (Schema)

本模块定义了认证相关的输入/输出数据结构：
1. Token: 登录/注册/刷新成功后返回的双 Token 结构
2. LoginRequest: 手机号密码登录请求参数
3. RegisterRequest: 用户注册请求参数
4. RefreshRequest: 刷新 Token 请求参数

Author: jinmozhe
Created: 2025-12-05
Updated: 2026-04-11 (Refactored phone_number to phone_code + mobile)
"""

from pydantic import BaseModel, EmailStr, Field, field_validator

# 从 core 层导入共享校验常量（避免跨领域导入）
from app.core.validators import (
    MOBILE_ERROR_MESSAGE,
    MOBILE_PATTERN,
    PHONE_CODE_ERROR_MESSAGE,
    PHONE_CODE_PATTERN,
)


class Token(BaseModel):
    """
    双 Token 响应结构 (Access + Refresh)。
    """

    access_token: str = Field(..., description="访问令牌 (JWT, 短效)")
    refresh_token: str = Field(..., description="刷新令牌 (随机串, 长效, 用于续期)")
    token_type: str = Field(default="bearer", description="令牌类型 (通常为 bearer)")
    expires_in: int = Field(..., description="Access Token 有效期 (秒)")


class LoginRequest(BaseModel):
    """
    手机号密码登录请求参数。
    """

    phone_code: str = Field(
        default="+86",
        description="手机区号 (默认 +86)",
        examples=["+86"],
    )
    mobile: str = Field(
        ...,
        description="手机号码 (纯数字)",
        examples=["13800000000"],
    )
    password: str = Field(..., min_length=6, description="用户密码")

    @field_validator("phone_code", mode="before")
    @classmethod
    def default_phone_code(cls, v: str | None) -> str:
        if not v:
            return "+86"
        return v

    @field_validator("phone_code")
    @classmethod
    def validate_phone_code(cls, v: str) -> str:
        if not PHONE_CODE_PATTERN.match(v):
            raise ValueError(PHONE_CODE_ERROR_MESSAGE)
        return v

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        if not MOBILE_PATTERN.match(v):
            raise ValueError(MOBILE_ERROR_MESSAGE)
        return v


class RegisterRequest(BaseModel):
    """
    用户注册请求参数。
    """

    phone_code: str = Field(
        default="+86",
        description="手机区号 (默认 +86)",
        examples=["+86"],
    )
    mobile: str = Field(
        ...,
        description="手机号码 (纯数字)",
        examples=["13800000000"],
    )
    password: str = Field(..., min_length=6, max_length=128, description="用户密码")
    username: str | None = Field(
        default=None, min_length=3, max_length=50, description="用户名 (可选，唯一)"
    )
    email: EmailStr | None = Field(default=None, description="邮箱 (可选，唯一)")

    @field_validator("phone_code", mode="before")
    @classmethod
    def default_phone_code(cls, v: str | None) -> str:
        if not v:
            return "+86"
        return v

    @field_validator("phone_code")
    @classmethod
    def validate_phone_code(cls, v: str) -> str:
        if not PHONE_CODE_PATTERN.match(v):
            raise ValueError(PHONE_CODE_ERROR_MESSAGE)
        return v

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        if not MOBILE_PATTERN.match(v):
            raise ValueError(MOBILE_ERROR_MESSAGE)
        return v


class RefreshRequest(BaseModel):
    """
    刷新 Token 请求参数。
    """

    refresh_token: str = Field(..., description="有效的刷新令牌")
