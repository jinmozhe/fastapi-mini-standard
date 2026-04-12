"""
File: app/domains/carts/dependencies.py
Description: 购物车依赖抽象库

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Annotated, Optional

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.domains.carts.service import CartService


async def get_cart_service(db: AsyncSession = Depends(get_db)) -> CartService:
    return CartService(db)

CartServiceDep = Annotated[CartService, Depends(get_cart_service)]

# 设备指纹门禁 (游客车底盘)
DeviceIdHeader = Annotated[Optional[str], Header(alias="X-Device-Id")]
