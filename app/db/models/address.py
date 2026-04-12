"""
File: app/db/models/address.py
Description: 用户收货地址模型

设计原则：
- 同时存储行政区划文本名称与编码（供物流系统对接）
- 支持港澳 phone_code（+852/+853）
- is_default 互斥由 Service 层事务保证，不依赖数据库触发器

Author: jinmozhe
Created: 2026-04-12
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import UUIDModel


class UserAddress(UUIDModel):
    """
    用户收货地址
    表名：addresses（去掉 user_ 前缀）
    """
    __tablename__ = "addresses"

    # ------------------------------------------------------------------
    # 归属关系
    # ------------------------------------------------------------------
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="归属用户",
    )

    # ------------------------------------------------------------------
    # 地址标签
    # ------------------------------------------------------------------
    label: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="地址标签（家/公司/自定义）",
    )

    # ------------------------------------------------------------------
    # 收件人信息
    # ------------------------------------------------------------------
    receiver_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="收件人姓名",
    )
    phone_code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="+86",
        server_default="+86",
        comment="手机区号（+86/+852/+853 等）",
    )
    mobile: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="手机号",
    )

    # ------------------------------------------------------------------
    # 地理位置（文本 + 行政编码双存）
    # ------------------------------------------------------------------
    country_code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="CN",
        server_default="CN",
        comment="国家编码（默认 CN）",
    )
    province: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="省名称",
    )
    province_code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="省行政编码（如 440000）",
    )
    city: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="市名称",
    )
    city_code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="市行政编码（如 440100）",
    )
    district: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="区/县名称",
    )
    district_code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="区行政编码（如 440106）",
    )
    street_address: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="详细街道+门牌号",
    )
    postal_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="邮政编码（小程序 picker 有时返回为空）",
    )

    # ------------------------------------------------------------------
    # 默认标记
    # ------------------------------------------------------------------
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="是否为默认地址（互斥由 Service 层保证唯一性）",
    )

    __table_args__ = (
        Index("ix_addresses_user_id", "user_id"),
    )
