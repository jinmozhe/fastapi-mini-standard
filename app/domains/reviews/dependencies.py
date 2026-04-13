"""
File: app/domains/reviews/dependencies.py
Description: 评价领域依赖注入

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.domains.reviews.service import ReviewService


async def get_review_service(db: AsyncSession = Depends(get_db)) -> ReviewService:
    return ReviewService(db)


ReviewServiceDep = Annotated[ReviewService, Depends(get_review_service)]
