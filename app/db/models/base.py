"""
File: app/db/models/base.py
Description: ORM 模型基类与组件化定义

本模块采用"组件化组合" (Mixin) 模式，适用于电商系统的不同数据场景：
1. UUIDBase: [基础] 提供 UUID v7 主键 + 自动表名(智能 snake_case) + update 方法
2. TimestampMixin: [组件] 提供 created_at, updated_at (UTC, TIMESTAMPTZ)
3. SoftDeleteMixin: [组件] 提供 is_deleted, deleted_at (用于商品/用户等基础资料)
4. UUIDModel: [标准] 聚合了 UUIDBase + TimestampMixin (适用于 90% 的业务表)

Author: jinmozhe
Created: 2025-11-25
"""

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column
from uuid6 import uuid7

# PostgreSQL 约束命名约定
POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def resolve_table_name(name: str) -> str:
    """
    将驼峰命名 (CamelCase) 转换为蛇形命名 (snake_case)。

    优化逻辑：智能处理连续大写缩写。
    示例:
    - UserProfile -> user_profile
    - APIKey -> api_key
    - HTTPResponse -> http_response
    """
    # 1. 处理连续大写后跟小写的情况 (例如 HTTPResponse -> HTTP_Response)
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)

    # 2. 处理小写/数字后跟大写的情况 (例如 UserProfile -> User_Profile)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class Base(DeclarativeBase):
    """SQLAlchemy 声明式元类"""

    metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)


# ==============================================================================
# 1. 功能组件 (Mixins) - 按需插拔
# ==============================================================================


class TimestampMixin:
    """
    [组件] 时间戳混入类

    提供 created_at 和 updated_at 字段。
    规范：强制使用 UTC 时间存储 (TIMESTAMPTZ)，展示时再转本地时间。
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
        comment="创建时间 (UTC)",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        comment="更新时间 (UTC)",
    )


class SoftDeleteMixin:
    """
    [组件] 软删除混入类

    适用场景：商品、用户、优惠券等基础资料（保留历史引用）。
    不适用场景：订单、支付流水（应使用状态机 status）。
    """

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        # 使用 text() 显式声明 SQL 表达式，更严谨
        server_default=text("false"),
        nullable=False,
        comment="是否软删除",
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True, comment="删除时间 (UTC)"
    )


# ==============================================================================
# 2. 基础模型 (Base Models)
# ==============================================================================


class UUIDBase(Base):
    """
    [纯净版] 仅包含 ID 和 基础工具方法。

    适用场景：关联表 (如 OrderItem, UserRole) 或不需要时间戳的配置表。
    """

    __abstract__ = True

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """自动将类名转为蛇形命名 (snake_case)"""
        return resolve_table_name(cls.__name__)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7, comment="主键 (UUID v7)"
    )

    def update(self, **kwargs: Any) -> None:
        """
        [工具方法] 动态更新模型属性

        用法:
        user.update(**schema.model_dump(exclude_unset=True))
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


# ==============================================================================
# 3. 标准聚合模型 (Standard Model)
# ==============================================================================


class UUIDModel(UUIDBase, TimestampMixin):
    """
    [标准版] 全站通用的业务模型基类。

    组合了：
    1. UUIDBase (ID + Update + SnakeCase表名)
    2. TimestampMixin (UTC 创建/更新时间)

    用法示例：

    1. 普通业务表 (订单)：
       class Order(UUIDModel): ...
       -> 表名: order

    2. 需要软删除的表 (商品)：
       class Product(UUIDModel, SoftDeleteMixin): ...
       -> 表名: product

    3. 纯关联表 (订单项)：
       class OrderItem(UUIDBase): ...
       -> 表名: order_item
    """

    __abstract__ = True
