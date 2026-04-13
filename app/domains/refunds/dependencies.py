"""
File: app/domains/refunds/dependencies.py
Description: 售后退款依赖注入

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.domains.refunds.service import RefundService


async def get_refund_service(db: AsyncSession = Depends(get_db)) -> RefundService:
    return RefundService(db)


RefundServiceDep = Annotated[RefundService, Depends(get_refund_service)]
