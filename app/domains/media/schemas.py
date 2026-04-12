"""
File: app/domains/media/schemas.py
Description: 媒体相关的 Pydantic 响应模型

Author: jinmozhe
Created: 2026-04-12
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ImageUrls(BaseModel):
    """图片全规格展示 URL 集合"""
    original: str = Field(..., description="高清原图 URL")
    large: str = Field(..., description="标清展示大图 URL 1080px")
    thumb: str = Field(..., description="列表缩略图 URL 400px")


class MediaUploadResult(BaseModel):
    """文件上传成功后返回的统一格式"""
    file_key: str = Field(..., description="保存于数据库的唯一标识路径")
    urls: ImageUrls = Field(..., description="前端能直接访问的绝对路径组合")


class MediaAssetRead(BaseModel):
    """B 端素材库单条记录"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    admin_id: UUID | None
    file_key: str
    file_name: str
    file_size: int
    mime_type: str
    provider: str
    created_at: datetime
