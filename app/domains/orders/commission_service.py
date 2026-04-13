"""
File: app/domains/orders/commission_service.py
Description: 佣金结算引擎

核心三个方法：
- settle_commissions()   → 计算佣金 + 冻结/直接入账
- release_commissions()  → 订单完成时释放冻结佣金到可用余额
- revoke_commissions()   → 管理员强制取消时扣回冻结佣金

分佣时机由 settings.COMMISSION_SETTLE_ON 控制：
- "payment"    → 支付成功时冻结分佣，完成时释放
- "completion" → 确认收货时直接入账到可用余额

Author: jinmozhe
Created: 2026-04-13
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.db.models.commission import CommissionRecord
from app.db.models.order import Order
from app.domains.orders.constants import CommissionLevel, CommissionStatus
from app.domains.orders.repository import CommissionRepository
from app.domains.user_wallets.constants import BalanceChangeType
from app.domains.user_wallets.service import UserWalletService


class CommissionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CommissionRepository(db)
        self.wallet_service = UserWalletService(db)

    async def settle_commissions(self, order: Order) -> Decimal:
        """
        计算并发放佣金。

        根据买家的推荐人链，逐级查找分佣规则，计算佣金金额。
        - payment 模式：冻结到 frozen_balance
        - completion 模式：直接入 balance

        返回佣金总额（用于更新 order.commission_total）。
        """
        from app.domains.products.repository import (
            ProductLevelCommissionRepository,
            ProductCategoryRepository,
        )
        from app.db.models.user_level import UserLevelProfile

        now_iso = datetime.now(timezone.utc).isoformat()
        is_freeze_mode = settings.COMMISSION_SETTLE_ON == "payment"

        # 1. 查买家的推荐人链
        referrer_chain = await self._get_referrer_chain(order.user_id)
        if not referrer_chain:
            logger.info("commission_no_referrer", order_no=order.order_no)
            return Decimal("0.00")

        # 2. 查订单明细
        from app.domains.orders.repository import OrderRepository
        order_repo = OrderRepository(self.db)
        items = await order_repo.get_items(order.id)

        # 3. 逐级计算佣金（简化版：基于订单总额 × 等级通用分佣比例）
        # 完整版应逐商品查 商品级固定佣 → 分类级百分比佣 → 等级通用佣
        # v1 先使用等级通用分佣规则
        total_commission = Decimal("0.00")

        level_map = {
            0: CommissionLevel.FIRST,
            1: CommissionLevel.SECOND,
            2: CommissionLevel.OTHER,
        }

        for idx, referrer_id in enumerate(referrer_chain[:3]):
            level = level_map.get(idx)
            if not level:
                break

            # 查推荐人等级的分佣规则
            commission_amount = await self._calc_referrer_commission(
                referrer_id=referrer_id,
                order=order,
                items=items,
                commission_level=level,
            )

            if commission_amount <= Decimal("0.00"):
                continue

            # 创建佣金记录
            if is_freeze_mode:
                record = CommissionRecord(
                    order_id=order.id,
                    order_no=order.order_no,
                    buyer_id=order.user_id,
                    beneficiary_id=referrer_id,
                    commission_level=level,
                    amount=commission_amount,
                    status=CommissionStatus.FROZEN,
                    frozen_at=now_iso,
                )
                self.db.add(record)

                # 冻结到推荐人钱包
                await self.wallet_service.freeze_commission(
                    user_id=referrer_id,
                    amount=commission_amount,
                    ref_id=order.id,
                    remark=f"订单 {order.order_no} {level}佣金冻结",
                )
            else:
                record = CommissionRecord(
                    order_id=order.id,
                    order_no=order.order_no,
                    buyer_id=order.user_id,
                    beneficiary_id=referrer_id,
                    commission_level=level,
                    amount=commission_amount,
                    status=CommissionStatus.SETTLED,
                    settled_at=now_iso,
                )
                self.db.add(record)

                # 直接入可用余额
                await self.wallet_service.change_balance(
                    user_id=referrer_id,
                    amount_delta=commission_amount,
                    change_type=BalanceChangeType.COMMISSION_FIRST if level == CommissionLevel.FIRST
                        else BalanceChangeType.COMMISSION_SECOND if level == CommissionLevel.SECOND
                        else BalanceChangeType.COMMISSION_OTHER,
                    ref_id=order.id,
                    remark=f"订单 {order.order_no} {level}佣金",
                )

            total_commission += commission_amount
            logger.info(
                "commission_created",
                order_no=order.order_no,
                beneficiary_id=str(referrer_id),
                level=level,
                amount=str(commission_amount),
                mode="freeze" if is_freeze_mode else "direct",
            )

        return total_commission

    async def release_commissions(self, order: Order) -> None:
        """
        订单完成时释放冻结佣金到可用余额。
        仅在 COMMISSION_SETTLE_ON = "payment" 模式下有意义。
        """
        if settings.COMMISSION_SETTLE_ON != "payment":
            # completion 模式下，佣金在 settle_commissions 时已直接入账
            # 但需要在此时计算佣金
            commission_total = await self.settle_commissions(order)
            order.commission_total = commission_total
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        frozen_records = await self.repo.get_frozen_by_order(order.id)

        for record in frozen_records:
            await self.wallet_service.unfreeze_commission(
                user_id=record.beneficiary_id,
                amount=record.amount,
                ref_id=order.id,
                remark=f"订单 {order.order_no} 佣金释放",
            )
            record.status = CommissionStatus.SETTLED
            record.settled_at = now_iso

        logger.info(
            "commission_released",
            order_no=order.order_no,
            count=len(frozen_records),
        )

    async def revoke_commissions(self, order: Order) -> None:
        """
        管理员强制取消订单时扣回冻结佣金。
        从 frozen_balance 扣回，100% 安全。
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        frozen_records = await self.repo.get_frozen_by_order(order.id)

        for record in frozen_records:
            await self.wallet_service.revoke_frozen_commission(
                user_id=record.beneficiary_id,
                amount=record.amount,
                ref_id=order.id,
                remark=f"订单 {order.order_no} 取消，佣金扣回",
            )
            record.status = CommissionStatus.REVOKED
            record.revoked_at = now_iso
            record.revoke_reason = f"订单取消"

        logger.info(
            "commission_revoked",
            order_no=order.order_no,
            count=len(frozen_records),
        )

    # --------------------------------------------------------------------------
    # 内部辅助方法
    # --------------------------------------------------------------------------

    async def _get_referrer_chain(self, user_id: UUID) -> list[UUID]:
        """
        查询用户的推荐人链（最多 3 级）。
        user → referrer_1 → referrer_2 → referrer_3
        """
        from sqlalchemy import select
        from app.db.models.user_level import UserLevelProfile

        chain: list[UUID] = []
        current_id = user_id

        for _ in range(3):
            stmt = select(UserLevelProfile.referrer_id).where(
                UserLevelProfile.user_id == current_id
            )
            referrer_id = await self.db.scalar(stmt)
            if not referrer_id:
                break
            chain.append(referrer_id)
            current_id = referrer_id

        return chain

    async def _calc_referrer_commission(
        self,
        referrer_id: UUID,
        order: Order,
        items: list,
        commission_level: str,
    ) -> Decimal:
        """
        计算单个推荐人的佣金金额。

        v1 简化版：基于订单商品总额，查推荐人等级的通用分佣规则。
        完整版应逐商品查 商品级固定佣 → 分类级百分比佣 → 等级通用佣。
        """
        from sqlalchemy import select
        from app.db.models.user import User
        from app.db.models.user_level import UserLevel

        # 查推荐人等级
        stmt = select(User.level_id).where(User.id == referrer_id)
        level_id = await self.db.scalar(stmt)
        if not level_id:
            return Decimal("0.00")

        # 查等级分佣规则
        level = await self.db.get(UserLevel, level_id)
        if not level or not level.commission_rules:
            return Decimal("0.00")

        # commission_rules 结构: {"first_rate": 0.03, "second_rate": 0.02, "other_rate": 0.01}
        rules = level.commission_rules
        rate_key = f"{commission_level}_rate"
        rate = Decimal(str(rules.get(rate_key, 0)))

        if rate <= Decimal("0"):
            return Decimal("0.00")

        # 基于商品总额计算
        commission = (order.items_amount * rate).quantize(Decimal("0.01"))
        return commission
