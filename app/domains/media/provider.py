"""
File: app/domains/media/provider.py
Description: 存储提供者抽象与本地存储实现

Author: jinmozhe
Created: 2026-04-12
"""

import os
from abc import ABC, abstractmethod
from typing import BinaryIO

from fastapi import Request


class StorageProvider(ABC):
    """存储驱动抽象基类"""
    
    @abstractmethod
    def save(self, file_content: bytes, file_key: str) -> None:
        """保存物理文件内容到对应的 file_key 路径"""
        pass
        
    @abstractmethod
    def delete(self, file_key: str) -> None:
        """物理删除"""
        pass

    @abstractmethod
    def get_url(self, file_key: str, request: Request) -> str:
        """获取完全的绝对访问 URL"""
        pass


class LocalStorageProvider(StorageProvider):
    """
    本地上传存储方案。
    将文件保存在项目的 uploads/ 夹，通过 FastAPI StaticFiles 托管。
    """
    
    # 根目录下的 uploads 文件夹
    BASE_DIR = "uploads"
    
    def __init__(self):
        # 确保根目录存在
        os.makedirs(self.BASE_DIR, exist_ok=True)

    def _get_absolute_path(self, file_key: str) -> str:
        # 去掉头部多余的斜杠防止拼接出错
        safe_key = file_key.lstrip("/")
        return os.path.join(self.BASE_DIR, safe_key)

    def save(self, file_content: bytes, file_key: str) -> None:
        abs_path = self._get_absolute_path(file_key)
        
        # 确保文件所在的目录存在
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        
        with open(abs_path, "wb") as f:
            f.write(file_content)

    def delete(self, file_key: str) -> None:
        abs_path = self._get_absolute_path(file_key)
        if os.path.exists(abs_path):
            os.remove(abs_path)

    def get_url(self, file_key: str, request: Request) -> str:
        """
        利用 Request 动态拼接 host
        例如: http://127.0.0.1:8000/uploads/products/xxx.jpg
        """
        # 注意 request.base_url 已经包含 scheme 和 netloc，且以 / 结尾
        safe_key = file_key.lstrip("/")
        return f"{request.base_url}uploads/{safe_key}"
