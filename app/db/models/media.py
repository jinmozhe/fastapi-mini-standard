"""
File: app/db/models/media.py
Description: 媒体素材记录模型

Author: jinmozhe
Created: 2026-04-12
"""

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import UUIDModel


class MediaAsset(UUIDModel):
    """
    媒体资产表 (素材库)
    存储所有上传的源文件记录，作为以后查询/复用的中心。
    约定：生成的缩略图或标清图不在这里单独占位，只有 Original 图才算入库。
    """
    __tablename__ = "media_assets"

    admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("sys_admins.id", ondelete="SET NULL"),
        nullable=True,
        comment="上传的管理员ID",
    )
    file_key: Mapped[str] = mapped_column(
        String(500), unique=True, index=True, nullable=False, comment="核心源路径 (如 products/123.jpg)"
    )
    file_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="源文件名 (包含后缀)"
    )
    file_size: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="文件字节大小"
    )
    mime_type: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="MIME 类型"
    )
    provider: Mapped[str] = mapped_column(
        String(20), default="local", nullable=False, comment="存储提供商标识 (local/oss/s3)"
    )
