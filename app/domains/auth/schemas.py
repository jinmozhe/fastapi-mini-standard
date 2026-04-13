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
    password: str = Field(..., min_length=6, max_length=128, description="用户密码")
    captcha_ticket: str = Field(default="", description="验证码凭证/票据 (开启防刷时必传)")
    captcha_randstr: str = Field(default="", description="验证码随机串 (腾讯云接口需配合传入)")

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
    invite_code: str | None = Field(
        default=None, min_length=4, max_length=20, description="邀请码 (可选，绑定推荐人)"
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


# ==============================================================================
# 多渠道登录请求模型
# ==============================================================================


class SmsCodeRequest(BaseModel):
    """
    发送短信验证码请求。
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


class SmsLoginRequest(BaseModel):
    """
    短信验证码登录请求 (注册即登录)。
    如果该手机号尚未注册，系统将自动创建账号。
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
    code: str = Field(
        ...,
        min_length=4,
        max_length=8,
        description="短信验证码",
        examples=["888888"],
    )
    inviter_id: str | None = Field(
        default=None,
        description="推荐人用户 ID (可选，用于分销关系绑定)",
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
        if not PHONE_CODE_PATTERN.match(v):
            raise ValueError(PHONE_CODE_ERROR_MESSAGE)
        return v

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        if not MOBILE_PATTERN.match(v):
            raise ValueError(MOBILE_ERROR_MESSAGE)
        return v


class WechatLoginRequest(BaseModel):
    """
    微信小程序授权登录请求。
    前端调用 wx.login() 获取 code，调用 wx.getPhoneNumber() 获取加密手机号。
    """

    js_code: str = Field(
        ...,
        description="wx.login() 返回的临时登录凭证 code",
    )
    encrypted_data: str = Field(
        ...,
        description="wx.getPhoneNumber() 返回的加密数据",
    )
    iv: str = Field(
        ...,
        description="加密算法初始向量",
    )
    inviter_id: str | None = Field(
        default=None,
        description="推荐人用户 ID (可选，用于分销关系绑定)",
    )


# ==============================================================================
# 社交绑定 / 网页扫码登录模型
# ==============================================================================


class WechatBindRequest(BaseModel):
    """
    已登录用户绑定微信请求。
    前端唤起微信授权获取 code（小程序用 wx.login()，网页用 OAuth 回调）。
    """

    code: str = Field(
        ...,
        description="微信授权 code（小程序或开放平台均可）",
    )
    platform: str = Field(
        default="wechat_mini",
        description="绑定平台: wechat_mini / wechat_mp / wechat_web",
    )


class WechatScanRequest(BaseModel):
    """
    网页端微信扫码登录请求。
    前端引导用户到微信扫码页 → 拿到回调 code → 提交给后端。
    """

    code: str = Field(
        ...,
        description="微信开放平台 OAuth 回调的 code",
    )


class WechatScanResponse(BaseModel):
    """
    网页扫码登录的响应。
    老用户：直接返回 token；
    新用户：返回 temp_token，前端需引导用户绑定手机号。
    """

    is_new: bool = Field(
        ...,
        description="是否为新用户（需要绑定手机号）",
    )
    token: Token | None = Field(
        default=None,
        description="已有用户的正式 Token（is_new=false 时返回）",
    )
    temp_token: str | None = Field(
        default=None,
        description="新用户的临时凭证（is_new=true 时返回，用于 /wechat/complete）",
    )
    nickname: str | None = Field(
        default=None,
        description="微信昵称（供前端预填）",
    )
    avatar: str | None = Field(
        default=None,
        description="微信头像 URL（供前端预填）",
    )


class WechatCompleteRequest(BaseModel):
    """
    网页扫码登录 — 完成注册（绑定手机号）。
    新用户扫码后必须验证手机号才能完成注册。
    """

    temp_token: str = Field(
        ...,
        description="扫码时返回的临时凭证",
    )
    phone_code: str = Field(
        default="+86",
        description="手机区号",
    )
    mobile: str = Field(
        ...,
        description="手机号码",
        examples=["13800000000"],
    )
    code: str = Field(
        ...,
        min_length=4,
        max_length=8,
        description="短信验证码",
    )
    inviter_id: str | None = Field(
        default=None,
        description="推荐人用户 ID",
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
        if not PHONE_CODE_PATTERN.match(v):
            raise ValueError(PHONE_CODE_ERROR_MESSAGE)
        return v

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        if not MOBILE_PATTERN.match(v):
            raise ValueError(MOBILE_ERROR_MESSAGE)
        return v


# ==============================================================================
# 密码管理模型
# ==============================================================================


class SetPasswordRequest(BaseModel):
    """
    设置/修改密码请求。
    - 首次设置密码（无密码用户）：old_password 可不传
    - 修改已有密码：old_password 必传
    """

    new_password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="新密码 (最少 6 位)",
    )
    old_password: str | None = Field(
        default=None,
        description="旧密码（已有密码的用户必传）",
    )
