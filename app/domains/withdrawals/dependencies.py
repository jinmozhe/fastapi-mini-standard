"""
File: app/domains/withdrawals/dependencies.py
Description: 提现领域依赖注入

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.domains.withdrawals.service import WithdrawalService


async def get_withdrawal_service(db: AsyncSession = Depends(get_db)) -> WithdrawalService:
    return WithdrawalService(db)


WithdrawalServiceDep = Annotated[WithdrawalService, Depends(get_withdrawal_service)]
