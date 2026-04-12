"""
File: app/domains/media/constants.py
Description: 媒体相关的常量配置与错误码定义

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Set
from app.core.exceptions import BaseErrorCode

# ==============================================================================
# 配置参数
# ==============================================================================


# 允许上传的图片 MIME 类型
ALLOWED_IMAGE_MIMES: Set[str] = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

# 单个文件大小上限 (例如 5MB)
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

# 缩略图派生尺寸
THUMB_MAX_EDGE = 400
LARGE_MAX_EDGE = 1080


# ==============================================================================
# 错误码
# ==============================================================================


class MediaError(BaseErrorCode):
    """文件处理领域错误码"""
    FILE_TOO_LARGE = (400, "media.file_too_large", f"文件大小超过限制 (最大 {MAX_FILE_SIZE_BYTES // 1024 // 1024}MB)")
    INVALID_FILE_TYPE = (400, "media.invalid_file_type", "不支持的文件类型")
    UPLOAD_FAILED = (500, "media.upload_failed", "文件上传失败")
    FILE_NOT_FOUND = (404, "media.not_found", "资源未找到")
