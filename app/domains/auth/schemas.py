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
Updated: 2026-04-03 (新增 RegisterRequest)
"""

from pydantic import BaseModel, EmailStr, Field, field_validator

# 复用 User 领域的正则常量，保持全站规则一致
from app.domains.users.schemas import E164_ERROR_MESSAGE, E164_PATTERN


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

    phone_number: str = Field(
        ...,
        description="手机号 (E.164 格式)",
        examples=["+8613800000000"],
    )
    password: str = Field(..., min_length=6, description="用户密码")

    @field_validator("phone_number")
    @classmethod
    def validate_e164(cls, v: str) -> str:
        """验证手机号格式"""
        if not E164_PATTERN.match(v):
            raise ValueError(E164_ERROR_MESSAGE)
        return v


class RegisterRequest(BaseModel):
    """
    用户注册请求参数。
    """

    phone_number: str = Field(
        ...,
        description="手机号 (E.164 格式)",
        examples=["+8613800000000"],
    )
    password: str = Field(..., min_length=6, max_length=128, description="用户密码")
    username: str | None = Field(
        default=None, min_length=3, max_length=50, description="用户名 (可选，唯一)"
    )
    email: EmailStr | None = Field(default=None, description="邮箱 (可选，唯一)")

    @field_validator("phone_number")
    @classmethod
    def validate_e164(cls, v: str) -> str:
        """验证手机号格式"""
        if not E164_PATTERN.match(v):
            raise ValueError(E164_ERROR_MESSAGE)
        return v


class RefreshRequest(BaseModel):
    """
    刷新 Token 请求参数。
    """

    refresh_token: str = Field(..., description="有效的刷新令牌")
