"""
File: app/domains/orders/dependencies.py
Description: 订单领域依赖注入

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.domains.orders.service import OrderService


async def get_order_service(db: AsyncSession = Depends(get_db)) -> OrderService:
    return OrderService(db)


OrderServiceDep = Annotated[OrderService, Depends(get_order_service)]
