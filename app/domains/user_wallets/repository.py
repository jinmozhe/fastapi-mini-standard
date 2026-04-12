"""
File: app/domains/user_wallets/repository.py
Description: 用户钱包领域的通用数据库操作仓储层。

Author: jinmozhe
Created: 2026-04-12
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user_wallet import UserBalanceLog, UserPointLog, UserWallet


class UserWalletRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.model = UserWallet

    async def get_by_user_id(self, user_id: UUID) -> UserWallet | None:
        """
        根据 user_id 查询钱包。
        """
        stmt = select(self.model).where(self.model.user_id == user_id)
        return await self.session.scalar(stmt)

    async def update_balance_with_optimistic_lock(
        self,
        wallet_id: UUID,
        current_version: int,
        amount_delta: Decimal,
        new_version: int,
    ) -> int:
        """
        乐观锁更新资金余额。
        :return: 影响的行数 (1则成功，0则失败代表发生并发冲突)
        """
        stmt = (
            update(self.model)
            .where(
                self.model.id == wallet_id,
                self.model.version == current_version,
            )
            .values(
                balance=self.model.balance + amount_delta,
                version=new_version,
            )
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    async def update_points_with_optimistic_lock(
        self,
        wallet_id: UUID,
        current_version: int,
        points_delta: int,
        new_version: int,
    ) -> int:
        """
        乐观锁更新积分。
        """
        stmt = (
            update(self.model)
            .where(
                self.model.id == wallet_id,
                self.model.version == current_version,
            )
            .values(
                points=self.model.points + points_delta,
                version=new_version,
            )
        )
        result = await self.session.execute(stmt)
        return result.rowcount


class UserBalanceLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.model = UserBalanceLog


class UserPointLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.model = UserPointLog

