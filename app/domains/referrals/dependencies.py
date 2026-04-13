"""
File: app/domains/referrals/dependencies.py
Description: 推荐关系依赖注入

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.domains.referrals.service import ReferralService


async def get_referral_service(db: AsyncSession = Depends(get_db)) -> ReferralService:
    return ReferralService(db)


ReferralServiceDep = Annotated[ReferralService, Depends(get_referral_service)]
