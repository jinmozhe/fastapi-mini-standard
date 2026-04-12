"""
File: app/domains/media/repository.py
Description: 媒体相关的持久化仓储

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.media import MediaAsset


class MediaRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.model = MediaAsset

    async def create(self, **kwargs) -> MediaAsset:
        db_obj = self.model(**kwargs)
        self.session.add(db_obj)
        await self.session.flush()
        return db_obj

    async def get_by_id(self, asset_id: UUID) -> MediaAsset | None:
        return await self.session.get(self.model, asset_id)
        
    async def get_list(self, skip: int = 0, limit: int = 20) -> Sequence[MediaAsset]:
        stmt = select(self.model).order_by(self.model.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.scalars(stmt)
        return result.all()

    async def delete(self, asset: MediaAsset) -> None:
        await self.session.delete(asset)
        await self.session.flush()
