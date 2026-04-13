"""
File: app/domains/payments/dependencies.py
Description: 支付领域依赖注入

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.domains.payments.service import PaymentService


async def get_payment_service(db: AsyncSession = Depends(get_db)) -> PaymentService:
    return PaymentService(db)


PaymentServiceDep = Annotated[PaymentService, Depends(get_payment_service)]
