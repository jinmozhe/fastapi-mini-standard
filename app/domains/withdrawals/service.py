"""
File: app/domains/withdrawals/service.py
Description: 提现核心业务引擎

核心流程：
1. apply_withdrawal()     → 用户申请提现（扣余额 → 冻结）
2. review_withdrawal()    → 管理员审核（通过/驳回）
3. complete_withdrawal()  → 管理员确认打款完成

资金联动：
- 申请：balance -= amount, frozen_balance += amount（通过 WalletService）
- 通过：仅标记状态，等待打款
- 完成：frozen_balance -= amount（真正扣减）
- 驳回：frozen_balance -= amount, balance += amount（退回）

Author: jinmozhe
Created: 2026-04-13
"""

import uuid as uuid_mod
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.logging import logger
from app.db.models.withdrawal import WithdrawalRecord
from app.domains.user_wallets.constants import BalanceChangeType
from app.domains.user_wallets.service import UserWalletService
from app.domains.withdrawals.constants import (
    MIN_WITHDRAW_AMOUNT,
    WITHDRAW_FEE_RATE,
    WithdrawalChannel,
    WithdrawalError,
    WithdrawalStatus,
)
from app.domains.withdrawals.repository import WithdrawalRepository
from app.domains.withdrawals.schemas import WithdrawApplyReq, WithdrawApplyResult


class WithdrawalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = WithdrawalRepository(db)
        self.wallet_service = UserWalletService(db)

    # --------------------------------------------------------------------------
    # 提现单号生成
    # --------------------------------------------------------------------------
    @staticmethod
    def _generate_withdrawal_no() -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        rand = str(uuid_mod.uuid4().int)[:6]
        return f"WD{ts}{rand}"

    # --------------------------------------------------------------------------
    # 1. 用户申请提现
    # --------------------------------------------------------------------------
    async def apply_withdrawal(
        self,
        user_id: UUID,
        data: WithdrawApplyReq,
    ) -> WithdrawApplyResult:
        """
        用户申请提现。

        校验：
        1. 提现通道合法
        2. 金额 >= 最低限额
        3. 无进行中的提现
        4. 可用余额充足

        资金操作：balance -= amount → frozen_balance += amount
        """
        # 通道校验
        valid_channels = {c.value for c in WithdrawalChannel}
        if data.channel not in valid_channels:
            raise AppException(WithdrawalError.INVALID_CHANNEL)

        # 最低限额
        if data.amount < MIN_WITHDRAW_AMOUNT:
            raise AppException(WithdrawalError.BELOW_MIN_AMOUNT)

        # 检查是否有进行中的提现
        pending = await self.repo.get_pending_by_user(user_id)
        if pending:
            raise AppException(WithdrawalError.PENDING_EXISTS)

        # 计算手续费
        fee = (data.amount * WITHDRAW_FEE_RATE).quantize(Decimal("0.01"))
        actual_amount = data.amount - fee

        # 扣余额冻结（原子乐观锁）
        wallet = await self.wallet_service.get_or_create_wallet(user_id)
        if wallet.balance < data.amount:
            raise AppException(WithdrawalError.INSUFFICIENT_BALANCE)

        # 扣减可用余额
        await self.wallet_service.change_balance(
            user_id=user_id,
            amount_delta=-data.amount,
            change_type=BalanceChangeType.WITHDRAW_APPLY,
            ref_id=None,
            remark=f"提现申请冻结 {data.amount} 元",
        )

        # 增加冻结余额
        await self.wallet_service.freeze_commission(
            user_id=user_id,
            amount=data.amount,
            ref_id=None,
            remark=f"提现冻结 {data.amount} 元",
        )

        # 创建提现记录
        record = WithdrawalRecord(
            withdrawal_no=self._generate_withdrawal_no(),
            user_id=user_id,
            amount=data.amount,
            fee=fee,
            actual_amount=actual_amount,
            channel=data.channel,
            account_info=data.account_info,
            status=WithdrawalStatus.PENDING,
            remark=data.remark,
        )
        self.db.add(record)
        await self.db.flush()

        logger.info(
            "withdrawal_applied",
            withdrawal_no=record.withdrawal_no,
            user_id=str(user_id),
            amount=str(data.amount),
            channel=data.channel,
        )

        return WithdrawApplyResult(
            withdrawal_id=record.id,
            withdrawal_no=record.withdrawal_no,
            amount=record.amount,
            fee=record.fee,
            actual_amount=record.actual_amount,
            status=record.status,
        )

    # --------------------------------------------------------------------------
    # 2. 管理员审核
    # --------------------------------------------------------------------------
    async def review_withdrawal(
        self,
        withdrawal_id: UUID,
        action: str,
        admin_id: UUID | None = None,
        admin_remark: str | None = None,
    ) -> None:
        """
        管理员审核提现。

        - approve: 通过 → 状态变为 approved（等待打款）
        - reject: 驳回 → 冻结退回余额
        """
        record = await self.repo.get_by_id(withdrawal_id)
        if not record:
            raise AppException(WithdrawalError.NOT_FOUND)

        if record.status != WithdrawalStatus.PENDING:
            raise AppException(WithdrawalError.INVALID_STATUS)

        now_iso = datetime.now(timezone.utc).isoformat()

        if action == "approve":
            record.status = WithdrawalStatus.APPROVED
            record.reviewed_at = now_iso
            record.reviewed_by = admin_id
            record.admin_remark = admin_remark

            logger.info("withdrawal_approved", withdrawal_no=record.withdrawal_no)

        elif action == "reject":
            record.status = WithdrawalStatus.REJECTED
            record.rejected_at = now_iso
            record.reviewed_by = admin_id
            record.admin_remark = admin_remark

            # 退回冻结到可用余额
            await self.wallet_service.revoke_frozen_commission(
                user_id=record.user_id,
                amount=record.amount,
                ref_id=record.id,
                remark=f"提现驳回 {record.withdrawal_no}，退回 {record.amount} 元",
            )
            await self.wallet_service.change_balance(
                user_id=record.user_id,
                amount_delta=record.amount,
                change_type=BalanceChangeType.WITHDRAW_REJECT,
                ref_id=record.id,
                remark=f"提现驳回 {record.withdrawal_no}，退回 {record.amount} 元",
            )

            logger.info("withdrawal_rejected", withdrawal_no=record.withdrawal_no)
        else:
            raise AppException(
                WithdrawalError.INVALID_STATUS,
                message="action 必须为 approve 或 reject",
            )

    # --------------------------------------------------------------------------
    # 3. 管理员确认打款完成
    # --------------------------------------------------------------------------
    async def complete_withdrawal(self, withdrawal_id: UUID) -> None:
        """
        管理员确认打款完成。
        从 frozen_balance 最终扣减。
        """
        record = await self.repo.get_by_id(withdrawal_id)
        if not record:
            raise AppException(WithdrawalError.NOT_FOUND)

        if record.status != WithdrawalStatus.APPROVED:
            raise AppException(WithdrawalError.INVALID_STATUS)

        now_iso = datetime.now(timezone.utc).isoformat()

        # 最终扣减冻结余额
        await self.wallet_service.revoke_frozen_commission(
            user_id=record.user_id,
            amount=record.amount,
            ref_id=record.id,
            remark=f"提现完成 {record.withdrawal_no}，实际到账 {record.actual_amount} 元",
        )

        record.status = WithdrawalStatus.COMPLETED
        record.completed_at = now_iso

        logger.info(
            "withdrawal_completed",
            withdrawal_no=record.withdrawal_no,
            actual_amount=str(record.actual_amount),
        )
