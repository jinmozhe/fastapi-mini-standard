"""
File: app/domains/user_wallets/dependencies.py
Description: 用户钱包领域依赖项容器。

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.domains.user_wallets.service import UserWalletService


async def get_wallet_service(db: AsyncSession = Depends(get_db)) -> UserWalletService:
    """提供 UserWalletService 单例"""
    return UserWalletService(db)


WalletServiceDep = Annotated[UserWalletService, Depends(get_wallet_service)]
