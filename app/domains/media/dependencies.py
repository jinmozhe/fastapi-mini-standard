"""
File: app/domains/media/dependencies.py
Description: 媒体相关的依赖注入

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.domains.media.service import MediaService


async def get_media_service(db: AsyncSession = Depends(get_db)) -> MediaService:
    return MediaService(db)


MediaServiceDep = Annotated[MediaService, Depends(get_media_service)]
