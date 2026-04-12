"""
File: app/domains/media/service.py
Description: 媒体文件核心业务层（含上传、Pillow 切片生成）

Author: jinmozhe
Created: 2026-04-12
"""

import io
import uuid
from datetime import datetime
from typing import Tuple

from fastapi import Request, UploadFile
from PIL import Image, ImageOps
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.logging import logger
from app.domains.media.constants import (
    ALLOWED_IMAGE_MIMES,
    LARGE_MAX_EDGE,
    MAX_FILE_SIZE_BYTES,
    THUMB_MAX_EDGE,
    MediaError,
)
from app.domains.media.provider import LocalStorageProvider, StorageProvider
from app.domains.media.repository import MediaRepository
from app.domains.media.schemas import ImageUrls, MediaUploadResult


class MediaService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MediaRepository(db)
        # 固定使用本地 Provider，未来若接入 OSS 可在此处注入分支
        self.provider: StorageProvider = LocalStorageProvider()

    def _generate_file_key(self, ext: str) -> str:
        """生成不可预测的相对路径"""
        date_str = datetime.now().strftime("%Y%m")
        unique_id = uuid.uuid4().hex
        return f"products/{date_str}/{unique_id}{ext}"

    def _process_image_sync(self, orig_bytes: bytes, mime_type: str) -> Tuple[bytes | None, bytes | None]:
        """
        同步调用 Pillow 进行派生图生成。
        :return: (large_bytes, thumb_bytes) 或 None 当处理失败时
        """
        try:
            # Pillow format 映射
            fmt_map = {
                "image/jpeg": "JPEG",
                "image/png": "PNG",
                "image/webp": "WEBP",
                "image/gif": "GIF",
            }
            save_format = fmt_map.get(mime_type, "JPEG")

            with Image.open(io.BytesIO(orig_bytes)) as img:
                # 转换 RGB 防止 PNG 的透明信道在转 JPEG 时报错
                if save_format == "JPEG" and img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # 生成 Large 图 (最大边 1080px，保持比例)
                img_large = img.copy()
                img_large.thumbnail((LARGE_MAX_EDGE, LARGE_MAX_EDGE), resample=Image.Resampling.LANCZOS)
                buf_large = io.BytesIO()
                img_large.save(buf_large, format=save_format, quality=85, optimize=True)
                large_bytes = buf_large.getvalue()

                # 生成 Thumb 图 (锁定 400x400 中心裁剪，电商极速方形标准)
                img_thumb = img.copy()
                img_thumb = ImageOps.fit(img_thumb, (THUMB_MAX_EDGE, THUMB_MAX_EDGE), method=Image.Resampling.LANCZOS)
                buf_thumb = io.BytesIO()
                img_thumb.save(buf_thumb, format=save_format, quality=80, optimize=True)
                thumb_bytes = buf_thumb.getvalue()

                return large_bytes, thumb_bytes

        except Exception as e:
            logger.error("image_process_failed", error=str(e))
            return None, None

    async def upload_image(self, file: UploadFile, admin_id: uuid.UUID, request: Request) -> MediaUploadResult:
        """接收上传，防雷校验，生成切片，入库并返回动态结构"""
        
        # 1. MIME 拦截
        if file.content_type not in ALLOWED_IMAGE_MIMES:
            raise AppException(MediaError.INVALID_FILE_TYPE)

        # 2. 读取入内存并校验大小
        content = await file.read()
        file_size = len(content)
        if file_size > MAX_FILE_SIZE_BYTES:
            raise AppException(MediaError.FILE_TOO_LARGE)

        # 3. 解析后缀名
        filename = file.filename or "unknown.jpg"
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()
        if not ext:
            ext = ".jpg"

        # 4. 生成基准名
        main_key = self._generate_file_key(ext)
        large_key = main_key.replace(ext, f"_large{ext}")
        thumb_key = main_key.replace(ext, f"_thumb{ext}")

        # 5. Pillow 衍生处理 (因为是内存操作且文件限制在了5MB，直接同步执行开销不大)
        large_bytes, thumb_bytes = self._process_image_sync(content, file.content_type)
        
        # 6. Physical Save
        self.provider.save(content, main_key)
        
        # 宽容处理：如果 Pillow 崩了，就不生成或者 fallback 为源图
        if large_bytes:
            self.provider.save(large_bytes, large_key)
        else:
            self.provider.save(content, large_key)

        if thumb_bytes:
            self.provider.save(thumb_bytes, thumb_key)
        else:
            self.provider.save(content, thumb_key)

        # 7. 登记素材库 `MediaAsset` 保证未来能够溯源追查
        asset = await self.repo.create(
            admin_id=admin_id,
            file_key=main_key,
            file_name=filename,
            file_size=file_size,
            mime_type=file.content_type,
            provider="local"
        )
        logger.info("media_uploaded", asset_id=str(asset.id), key=main_key)

        # 8. 返回动态请求包装
        return MediaUploadResult(
            file_key=main_key,
            urls=ImageUrls(
                original=self.provider.get_url(main_key, request),
                large=self.provider.get_url(large_key, request),
                thumb=self.provider.get_url(thumb_key, request),
            )
        )

    async def get_admin_materials(self, skip: int, limit: int) -> list:
        return await self.repo.get_list(skip, limit)

    async def delete_material(self, asset_id: uuid.UUID) -> None:
        asset = await self.repo.get_by_id(asset_id)
        if not asset:
            raise AppException(MediaError.FILE_NOT_FOUND)
        
        # 物理截断 (为了保障历史订单展现，一般也可以不删物理图，这里做完整演示)
        ext = ""
        if "." in asset.file_key:
            ext = "." + asset.file_key.rsplit(".", 1)[-1]
        large_key = asset.file_key.replace(ext, f"_large{ext}")
        thumb_key = asset.file_key.replace(ext, f"_thumb{ext}")

        self.provider.delete(asset.file_key)
        self.provider.delete(large_key)
        self.provider.delete(thumb_key)

        await self.repo.delete(asset)
        logger.info("media_deleted", asset_id=str(asset_id))
