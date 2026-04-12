"""
File: app/domains/addresses/dependencies.py
Description: 地址领域依赖注入

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.domains.addresses.service import AddressService


async def get_address_service(db: AsyncSession = Depends(get_db)) -> AddressService:
    return AddressService(db)


AddressServiceDep = Annotated[AddressService, Depends(get_address_service)]
