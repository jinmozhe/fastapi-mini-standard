"""
File: app/db/models/user_social.py
Description: 用户三方绑定模型 (微信/Google等)

本表用于存储多渠道的三方登录凭证。
一个 User 可以对应多个 Social 记录 (如同时绑定微信小程序和公众号)。

注意：
采用 "No-Relationship" 模式，不显式定义 ORM relationship。
User 与 UserSocial 的关联仅通过 user_id 外键物理约束。
严禁使用物理级联删除，以配合系统的软删除策略。

Author: jinmozhe
Created: 2025-12-02
Updated: 2026-04-12 (补充 session_key / 唯一约束 / nickname / avatar)
"""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.db.models.base import UUIDModel


class UserSocial(UUIDModel):
    """
    用户三方绑定表 (N:1 User)

    关键设计：
    - platform + openid 唯一约束，防止同一三方账号重复绑定
    - session_key 用于微信小程序后续解密操作（如获取手机号）
    - extra_data 存储三方平台返回的原始数据快照
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "user_socials"

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return (
            # 同一平台同一 openid 只能绑定一次，防止脏数据
            UniqueConstraint("platform", "openid", name="uq_social_platform_openid"),
        )

    # --------------------------------------------------------------------------
    # 外键关联
    # --------------------------------------------------------------------------

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # 物理外键约束，保证数据完整性
        # ❌ 严禁 ondelete="CASCADE"：用户仅软删除，绑定关系必须保留
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="关联用户ID",
    )

    # --------------------------------------------------------------------------
    # 三方核心凭证
    # --------------------------------------------------------------------------

    # 平台标识: wechat_mini(小程序), wechat_mp(公众号), google, apple
    platform: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="平台标识"
    )

    # 三方唯一ID (OpenID / Sub)
    openid: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, comment="三方唯一ID(OpenID)"
    )

    # 跨应用统一ID (微信 UnionID)
    unionid: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True, comment="微信UnionID"
    )

    # 微信小程序会话密钥（用于后续解密手机号等敏感数据）
    session_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="微信 session_key (加密密钥)"
    )

    # --------------------------------------------------------------------------
    # 三方用户资料（同步保存，减少二次请求）
    # --------------------------------------------------------------------------

    # 三方平台昵称
    nickname: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="三方平台昵称"
    )

    # 三方平台头像
    avatar: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="三方平台头像URL"
    )

    # --------------------------------------------------------------------------
    # 扩展数据 (JSON)
    # --------------------------------------------------------------------------

    # 存储三方返回的原始数据快照
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, comment="三方原始数据快照"
    )
"""
File: app/db/models/user_social.py
"""
