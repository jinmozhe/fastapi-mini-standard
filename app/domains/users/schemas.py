"""
File: app/domains/users/schemas.py
Description: 用户领域 Pydantic 模型 (Schema)

本模块定义了用户相关的输入/输出数据结构：
1. UserUpdate: 用户更新参数 (所有字段可选)
2. UserRead: 用户信息响应 (包含 ID, 时间戳, 屏蔽密码)
3. 注册参数已移到 auth/schemas.py (RegisterRequest)

规范：
- 严格遵循 Pydantic V2 写法 (ConfigDict)
- 全面采用 Python 3.11+ 新语法 (X | None)
- 拆分 phone_code（默认 +86）与 mobile
- 响应模型开启 from_attributes=True 以支持 ORM 转换

Author: jinmozhe
Created: 2025-11-25
Updated: 2026-04-11 (Refactored phone_number to phone_code and mobile)
"""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# ------------------------------------------------------------------------------
# Constants (常量定义)
# ------------------------------------------------------------------------------

# 手机区号正则：以 + 开头，后接 1-4 位数字
PHONE_CODE_PATTERN = re.compile(r"^\+\d{1,4}$")
PHONE_CODE_ERROR_MESSAGE = "手机区号格式错误，应以 + 开头，后跟 1-4 位数字"

# 手机号正则：纯数字，5 到 15 位
MOBILE_PATTERN = re.compile(r"^\d{5,15}$")
MOBILE_ERROR_MESSAGE = "手机号格式错误，应为 5-15 位纯数字"


# ------------------------------------------------------------------------------
# Shared Properties (共享属性)
# ------------------------------------------------------------------------------


class UserBase(BaseModel):
    """
    用户基础属性基类。
    包含 Create 和 Read 共有的字段。
    """

    phone_code: str = Field(
        default="+86",
        description="手机区号 (默认 +86)",
        examples=["+86", "+852"],
    )
    mobile: str = Field(
        ...,
        description="手机号码 (纯数字)",
        examples=["13800000000"],
    )
    username: str | None = Field(
        default=None, min_length=3, max_length=50, description="用户名 (可选, 唯一)"
    )
    email: EmailStr | None = Field(default=None, description="邮箱 (可选, 唯一)")
    full_name: str | None = Field(
        default=None, max_length=100, description="用户全名/昵称"
    )

    @field_validator("phone_code", mode="before")
    @classmethod
    def default_phone_code(cls, v: str | None) -> str:
        if not v:
            return "+86"
        return v

    @field_validator("phone_code")
    @classmethod
    def validate_phone_code(cls, v: str) -> str:
        """验证手机区号格式"""
        if not PHONE_CODE_PATTERN.match(v):
            raise ValueError(PHONE_CODE_ERROR_MESSAGE)
        return v

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        """验证手机号格式"""
        if not MOBILE_PATTERN.match(v):
            raise ValueError(MOBILE_ERROR_MESSAGE)
        return v


# ------------------------------------------------------------------------------
# Input Schemas (输入模型)
# ------------------------------------------------------------------------------


class UserUpdate(BaseModel):
    """
    用户更新模型。
    所有字段均为可选，仅更新传入的字段 (PATCH 语义)。
    """

    phone_code: str | None = Field(
        default=None, description="新手机区号 (如 +86)"
    )
    mobile: str | None = Field(
        default=None, description="新手机号 (纯数字)"
    )
    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: EmailStr | None = Field(default=None)
    full_name: str | None = Field(default=None, max_length=100)
    password: str | None = Field(
        default=None, min_length=6, max_length=128, description="新密码 (如需修改)"
    )
    is_active: bool | None = Field(default=None, description="是否激活 (仅管理员可改)")

    @field_validator("phone_code", mode="before")
    @classmethod
    def default_phone_code(cls, v: str | None) -> str | None:
        if v == "":
            return "+86"
        return v

    @field_validator("phone_code")
    @classmethod
    def validate_phone_code(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not PHONE_CODE_PATTERN.match(v):
            raise ValueError(PHONE_CODE_ERROR_MESSAGE)
        return v

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not MOBILE_PATTERN.match(v):
            raise ValueError(MOBILE_ERROR_MESSAGE)
        return v


# ------------------------------------------------------------------------------
# Output Schemas (输出/响应模型)
# ------------------------------------------------------------------------------


class UserRead(UserBase):
    """
    用户读取模型 (响应)。
    屏蔽了 password 字段，增加了 id 和 系统管理字段。
    """

    id: UUID = Field(..., description="用户 ID (UUID v7)")
    is_active: bool = Field(..., description="账号状态")
    is_superuser: bool = Field(..., description="是否超级管理员")
    created_at: datetime = Field(..., description="创建时间 (UTC)")
    updated_at: datetime = Field(..., description="更新时间 (UTC)")

    # Pydantic V2 配置：允许从 ORM 对象读取数据
    model_config = ConfigDict(from_attributes=True)
