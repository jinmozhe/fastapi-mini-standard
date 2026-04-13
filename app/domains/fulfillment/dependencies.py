"""
File: app/domains/fulfillment/dependencies.py
Description: 履约领域依赖注入

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.domains.fulfillment.service import FulfillmentService


async def get_fulfillment_service(db: AsyncSession = Depends(get_db)) -> FulfillmentService:
    return FulfillmentService(db)


FulfillmentServiceDep = Annotated[FulfillmentService, Depends(get_fulfillment_service)]
