"""
File: app/domains/shipping/dependencies.py
Description: 运费模板领域依赖注入

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.domains.shipping.service import ShippingService


async def get_shipping_service(db: AsyncSession = Depends(get_db)) -> ShippingService:
    return ShippingService(db)


ShippingServiceDep = Annotated[ShippingService, Depends(get_shipping_service)]
