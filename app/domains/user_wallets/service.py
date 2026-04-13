"""
File: app/domains/user_wallets/service.py
Description: 用户钱包领域核心业务逻辑。
实现金额与积分的原子化乐观锁扣除，并强制写入流水铁账本。

Author: jinmozhe
Created: 2026-04-12
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.logging import logger
from app.db.models.user_wallet import UserBalanceLog, UserPointLog, UserWallet
from app.domains.user_wallets.constants import BalanceChangeType, PointChangeType, WalletError
from app.domains.user_wallets.repository import (
    UserBalanceLogRepository,
    UserPointLogRepository,
    UserWalletRepository,
)


class UserWalletService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.wallet_repo = UserWalletRepository(db)
        self.balance_log_repo = UserBalanceLogRepository(db)
        self.point_log_repo = UserPointLogRepository(db)

    async def get_or_create_wallet(self, user_id: UUID) -> UserWallet:
        """
        获取用户钱包，如果不存在则静默创建空钱包。
        保护高并发查询与向下兼容旧数据。
        """
        # 1. 尝试获取如果不存在则依赖里面的隐式add(不在begin中会导致连接问题吗？
        # 我们最好先检查有无，没有在事务中插入)
        wallet = await self.wallet_repo.get_by_user_id(user_id)
        if not wallet:
            # 静默创建空钱包
            wallet = UserWallet(user_id=user_id)
            self.db.add(wallet)
            await self.db.flush()
            logger.info("wallet_initialized", user_id=str(user_id))
        return wallet

    async def change_balance(
        self,
        user_id: UUID,
        amount_delta: Decimal,
        change_type: BalanceChangeType | str,
        ref_id: UUID | None = None,
        remark: str | None = None,
    ) -> UserWallet:
        """
        资金变动引擎：增加或扣减余额。
        采用乐观锁机制防止超卖，更新成功后必须同步持久化资金流水。

        :param user_id: 用户ID
        :param amount_delta: 变动金额 (正数为增，负数为减)
        :param change_type: 变动类型枚举
        :param ref_id: 业务相关外部单号 (如订单ID)
        :param remark: 变动备注
        :return: 更新后的钱包对象
        """
        if amount_delta == Decimal("0.00"):
            raise AppException(WalletError.INVALID_AMOUNT, message="变动金额不能为0")

        async with self.db.begin():
            wallet = await self.get_or_create_wallet(user_id)
    
            before_balance = wallet.balance
            after_balance = before_balance + amount_delta
    
            # 校验余额下限
            if after_balance < Decimal("0.00"):
                raise AppException(WalletError.INSUFFICIENT_BALANCE)
    
            # 准备乐观锁更新
            current_version = wallet.version
            new_version = current_version + 1
    
            # 执行带有版本号的 UPDATE 语句
            affected_rows = await self.wallet_repo.update_balance_with_optimistic_lock(
                wallet_id=wallet.id,
                current_version=current_version,
                amount_delta=amount_delta,
                new_version=new_version,
            )
    
            if affected_rows == 0:
                # 乐观锁未命中：在此期间被其他进程修改
                logger.warning(
                    "wallet_balance_concurrent_failed",
                    user_id=str(user_id),
                    version=current_version,
                    delta=str(amount_delta),
                )
                raise AppException(WalletError.CONCURRENT_UPDATE_FAILED, message="资金处理繁忙，请重试")
    
            # 更新对象状态以供后续使用 (因为直接 update 的 db 不会自动刷新 object)
            wallet.balance = after_balance
            wallet.version = new_version
    
            # 生成并插入资金流水铁账本
            log = UserBalanceLog(
                user_id=user_id,
                change_type=change_type,
                amount=amount_delta,
                before_balance=before_balance,
                after_balance=after_balance,
                ref_id=ref_id,
                remark=remark,
            )
            self.db.add(log)


        logger.info(
            "wallet_balance_changed",
            user_id=str(user_id),
            change_type=change_type,
            amount_delta=str(amount_delta),
            after_balance=str(after_balance),
            ref_id=str(ref_id),
        )

        return wallet

    async def change_points(
        self,
        user_id: UUID,
        points_delta: int,
        change_type: PointChangeType | str,
        ref_id: UUID | None = None,
        remark: str | None = None,
    ) -> UserWallet:
        """
        积分变动引擎：增加或扣减积分。
        与资金一样采用乐观锁与流水记账。
        """
        if points_delta == 0:
            raise AppException(WalletError.INVALID_AMOUNT, message="变动积分不能为0")

        async with self.db.begin():
            wallet = await self.get_or_create_wallet(user_id)
    
            before_points = wallet.points
            after_points = before_points + points_delta
    
            if after_points < 0:
                raise AppException(WalletError.INSUFFICIENT_POINTS)
    
            current_version = wallet.version
            new_version = current_version + 1
    
            affected_rows = await self.wallet_repo.update_points_with_optimistic_lock(
                wallet_id=wallet.id,
                current_version=current_version,
                points_delta=points_delta,
                new_version=new_version,
            )
    
            if affected_rows == 0:
                logger.warning(
                    "wallet_points_concurrent_failed",
                    user_id=str(user_id),
                    version=current_version,
                    delta=points_delta,
                )
                raise AppException(WalletError.CONCURRENT_UPDATE_FAILED, message="积分处理繁忙，请重试")
    
            wallet.points = after_points
            wallet.version = new_version
    
            # 积分流水账本
            log = UserPointLog(
                user_id=user_id,
                change_type=change_type,
                points=points_delta,
                before_points=before_points,
                after_points=after_points,
                ref_id=ref_id,
                remark=remark,
            )
            self.db.add(log)


        logger.info(
            "wallet_points_changed",
            user_id=str(user_id),
            change_type=change_type,
            points_delta=points_delta,
            after_points=after_points,
            ref_id=str(ref_id),
        )

        return wallet

    # --------------------------------------------------------------------------
    # 佣金冻结/释放/扣回引擎
    # --------------------------------------------------------------------------

    async def freeze_commission(
        self,
        user_id: UUID,
        amount: Decimal,
        ref_id: UUID | None = None,
        remark: str | None = None,
    ) -> UserWallet:
        """
        佣金冻结：将佣金金额加入 frozen_balance。
        佣金来源于买家支付，不从推荐人自有余额扣减。
        """
        if amount <= Decimal("0.00"):
            raise AppException(WalletError.INVALID_AMOUNT, message="冻结金额必须大于0")

        async with self.db.begin():
            wallet = await self.get_or_create_wallet(user_id)
            current_version = wallet.version
            new_version = current_version + 1

            affected = await self.wallet_repo.freeze_balance_with_optimistic_lock(
                wallet_id=wallet.id,
                current_version=current_version,
                amount=amount,
                new_version=new_version,
            )
            if affected == 0:
                raise AppException(WalletError.CONCURRENT_UPDATE_FAILED, message="佣金冻结处理繁忙，请重试")

            before_frozen = wallet.frozen_balance
            after_frozen = before_frozen + amount
            wallet.frozen_balance = after_frozen
            wallet.version = new_version

            # 冻结流水
            log = UserBalanceLog(
                user_id=user_id,
                change_type=BalanceChangeType.COMMISSION_FREEZE,
                amount=amount,
                before_balance=before_frozen,
                after_balance=after_frozen,
                ref_id=ref_id,
                remark=remark or "佣金冻结",
            )
            self.db.add(log)

        logger.info(
            "wallet_commission_frozen",
            user_id=str(user_id),
            amount=str(amount),
            after_frozen=str(after_frozen),
            ref_id=str(ref_id),
        )
        return wallet

    async def unfreeze_commission(
        self,
        user_id: UUID,
        amount: Decimal,
        ref_id: UUID | None = None,
        remark: str | None = None,
    ) -> UserWallet:
        """
        佣金释放：frozen_balance → balance。
        订单完成时将冻结佣金迁移到可用余额。
        """
        if amount <= Decimal("0.00"):
            raise AppException(WalletError.INVALID_AMOUNT, message="释放金额必须大于0")

        async with self.db.begin():
            wallet = await self.get_or_create_wallet(user_id)
            current_version = wallet.version
            new_version = current_version + 1

            affected = await self.wallet_repo.unfreeze_to_balance_with_optimistic_lock(
                wallet_id=wallet.id,
                current_version=current_version,
                amount=amount,
                new_version=new_version,
            )
            if affected == 0:
                raise AppException(WalletError.CONCURRENT_UPDATE_FAILED, message="佣金释放处理繁忙，请重试")

            wallet.frozen_balance -= amount
            wallet.balance += amount
            wallet.version = new_version

            # 释放流水
            log = UserBalanceLog(
                user_id=user_id,
                change_type=BalanceChangeType.COMMISSION_SETTLE,
                amount=amount,
                before_balance=wallet.balance - amount,
                after_balance=wallet.balance,
                ref_id=ref_id,
                remark=remark or "佣金释放到可用余额",
            )
            self.db.add(log)

        logger.info(
            "wallet_commission_settled",
            user_id=str(user_id),
            amount=str(amount),
            ref_id=str(ref_id),
        )
        return wallet

    async def revoke_frozen_commission(
        self,
        user_id: UUID,
        amount: Decimal,
        ref_id: UUID | None = None,
        remark: str | None = None,
    ) -> UserWallet:
        """
        佣金扣回：从 frozen_balance 扣除。
        管理员强制取消订单时调用，从冻结区扣回，100% 安全。
        """
        if amount <= Decimal("0.00"):
            raise AppException(WalletError.INVALID_AMOUNT, message="扣回金额必须大于0")

        async with self.db.begin():
            wallet = await self.get_or_create_wallet(user_id)
            current_version = wallet.version
            new_version = current_version + 1

            affected = await self.wallet_repo.deduct_frozen_with_optimistic_lock(
                wallet_id=wallet.id,
                current_version=current_version,
                amount=amount,
                new_version=new_version,
            )
            if affected == 0:
                logger.warning(
                    "wallet_commission_revoke_failed",
                    user_id=str(user_id),
                    amount=str(amount),
                    frozen_balance=str(wallet.frozen_balance),
                )
                raise AppException(WalletError.CONCURRENT_UPDATE_FAILED, message="佣金扣回处理繁忙，请重试")

            before_frozen = wallet.frozen_balance
            after_frozen = before_frozen - amount
            wallet.frozen_balance = after_frozen
            wallet.version = new_version

            # 扣回流水
            log = UserBalanceLog(
                user_id=user_id,
                change_type=BalanceChangeType.COMMISSION_REVOKE,
                amount=-amount,
                before_balance=before_frozen,
                after_balance=after_frozen,
                ref_id=ref_id,
                remark=remark or "取消订单扣回佣金",
            )
            self.db.add(log)

        logger.info(
            "wallet_commission_revoked",
            user_id=str(user_id),
            amount=str(amount),
            ref_id=str(ref_id),
        )
        return wallet

