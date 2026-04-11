"""
File: app/db/models/user.py
Description: 用户核心账号模型

本模型定义了用户核心数据结构。
继承自 UUIDModel 和 SoftDeleteMixin，自动拥有：
1. UUID v7 主键
2. created_at / updated_at (UTC)
3. is_deleted / deleted_at (软删除支持)

注意：
采用 "No-Relationship" 模式，不显式定义 ORM relationship。
如需查询关联数据（如 Profile），请在 Repository 层使用显式 JOIN 或单独查询。

Author: jinmozhe
Created: 2025-11-25
"""

from sqlalchemy import Boolean, String, text
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.db.models.base import SoftDeleteMixin, UUIDModel


class User(UUIDModel, SoftDeleteMixin):
    """
    用户模型 (账号域)
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "users"

    # --------------------------------------------------------------------------
    # 核心凭证
    # --------------------------------------------------------------------------

    # 手机号：核心登录凭证，必填且唯一
    phone_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        comment="手机号 (核心登录凭证, E.164格式)",
    )

    # 邮箱：辅助登录凭证，可为空
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, comment="用户邮箱"
    )

    # 用户名：备选登录凭证，可为空
    username: Mapped[str | None] = mapped_column(
        String(50), unique=True, nullable=True, comment="用户名"
    )

    # 密码：存储 Argon2id 或 Bcrypt 哈希值
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希值"
    )

    # --------------------------------------------------------------------------
    # 基础资料
    # --------------------------------------------------------------------------

    # 昵称：用于对外展示，可重复
    nickname: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="用户昵称 (显示用)"
    )

    # 头像：存储 URL
    avatar: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="头像URL"
    )

    # --------------------------------------------------------------------------
    # 状态与权限
    # --------------------------------------------------------------------------

    # 账号状态
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
        comment="是否激活",
    )

    # 超级管理员标记
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
        comment="是否超级管理员",
    )

    # 实名认证状态 (冗余字段，便于快速判断权限)
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
        comment="是否已实名认证",
    )
