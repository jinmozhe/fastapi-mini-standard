"""
File: app/domains/refunds/service.py
Description: 售后退款核心引擎

核心流程：
1. apply_refund()        → 买家申请退款
2. review_refund()       → 管理员审核（通过/驳回）
3. submit_return_info()  → 买家填退货运单号
4. confirm_return()      → 管理员确认收到退货 → 执行退款

退款联动：
- 调用 PaymentService.refund_payment() 退钱
- 调用 CommissionService.revoke_commissions() 扣回佣金
- 调用 ProductRepository.restore_stock() 恢复库存

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
from app.db.models.refund import RefundRecord
from app.domains.orders.constants import OrderStatus
from app.domains.orders.repository import OrderRepository
from app.domains.refunds.constants import RefundError, RefundStatus, RefundType
from app.domains.refunds.repository import RefundRepository
from app.domains.refunds.schemas import RefundApplyReq, RefundApplyResult


class RefundService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = RefundRepository(db)
        self.order_repo = OrderRepository(db)

    # --------------------------------------------------------------------------
    # 退款单号生成
    # --------------------------------------------------------------------------
    @staticmethod
    def _generate_refund_no() -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        rand = str(uuid_mod.uuid4().int)[:6]
        return f"RFD{ts}{rand}"

    # --------------------------------------------------------------------------
    # 1. 买家申请退款
    # --------------------------------------------------------------------------
    async def apply_refund(
        self,
        user_id: UUID,
        data: RefundApplyReq,
    ) -> RefundApplyResult:
        """
        买家申请退款。

        校验规则：
        1. 订单存在且属于当前用户
        2. 订单状态为 pending_shipment / shipped / completed（completed 仅退货退款）
        3. 商品 refundable = True
        4. 当前订单没有进行中的退款
        5. 退款金额不超过订单实付
        """
        from app.domains.products.repository import ProductRepository

        order = await self.order_repo.get_by_id(data.order_id)
        if not order or order.user_id != user_id:
            raise AppException(RefundError.ORDER_NOT_FOUND)

        # 状态校验
        allowed_statuses = {
            OrderStatus.PENDING_SHIPMENT,
            OrderStatus.SHIPPED,
            OrderStatus.COMPLETED,
        }
        if order.status not in allowed_statuses:
            raise AppException(RefundError.ORDER_STATUS_INVALID)

        # 已完成的订单只能退货退款
        if order.status == OrderStatus.COMPLETED and data.refund_type == RefundType.REFUND_ONLY:
            raise AppException(
                RefundError.ORDER_STATUS_INVALID,
                message="已完成订单仅支持退货退款",
            )

        # 商品退款权限校验
        product_repo = ProductRepository(self.db)
        items = await self.order_repo.get_items(order.id)
        for item in items:
            product = await product_repo.get_by_id(item.product_id)
            if product and not product.refundable:
                raise AppException(RefundError.NOT_REFUNDABLE)

        # 检查是否已有进行中的退款
        existing = await self.repo.get_active_by_order(order.id)
        if existing:
            raise AppException(RefundError.ALREADY_APPLIED)

        # 金额校验
        if data.refund_amount > order.total_amount:
            raise AppException(RefundError.AMOUNT_EXCEED)

        # 创建退款记录
        refund = RefundRecord(
            refund_no=self._generate_refund_no(),
            order_id=order.id,
            order_no=order.order_no,
            user_id=user_id,
            refund_type=data.refund_type,
            refund_amount=data.refund_amount,
            reason=data.reason,
            description=data.description,
            images=data.images,
            status=RefundStatus.PENDING,
        )
        self.db.add(refund)
        await self.db.flush()

        logger.info(
            "refund_applied",
            refund_no=refund.refund_no,
            order_no=order.order_no,
            refund_type=data.refund_type,
            amount=str(data.refund_amount),
        )

        return RefundApplyResult(
            refund_id=refund.id,
            refund_no=refund.refund_no,
            status=refund.status,
        )

    # --------------------------------------------------------------------------
    # 2. 管理员审核
    # --------------------------------------------------------------------------
    async def review_refund(
        self,
        refund_id: UUID,
        action: str,
        admin_remark: str | None = None,
    ) -> None:
        """
        管理员审核退款。

        - approve: 通过
          - refund_only → 直接执行退款 + 扣回佣金 + 恢复库存
          - return_refund → 状态变为 approved，等买家寄回
        - reject: 驳回
        """
        refund = await self.repo.get_by_id(refund_id)
        if not refund:
            raise AppException(RefundError.NOT_FOUND)

        if refund.status != RefundStatus.PENDING:
            raise AppException(RefundError.INVALID_STATUS)

        now_iso = datetime.now(timezone.utc).isoformat()

        if action == "approve":
            refund.status = RefundStatus.APPROVED
            refund.approved_at = now_iso
            refund.admin_remark = admin_remark

            # 仅退款 → 直接执行退款
            if refund.refund_type == RefundType.REFUND_ONLY:
                await self._execute_refund(refund)

            logger.info("refund_approved", refund_no=refund.refund_no)

        elif action == "reject":
            refund.status = RefundStatus.REJECTED
            refund.rejected_at = now_iso
            refund.admin_remark = admin_remark

            logger.info("refund_rejected", refund_no=refund.refund_no)
        else:
            raise AppException(RefundError.INVALID_STATUS, message="action 必须为 approve 或 reject")

    # --------------------------------------------------------------------------
    # 3. 买家填退货运单号
    # --------------------------------------------------------------------------
    async def submit_return_info(
        self,
        user_id: UUID,
        refund_id: UUID,
        return_company: str,
        return_tracking_no: str,
    ) -> None:
        """买家填写退货运单号"""
        refund = await self.repo.get_by_id(refund_id)
        if not refund or refund.user_id != user_id:
            raise AppException(RefundError.NOT_FOUND)

        if refund.status != RefundStatus.APPROVED:
            raise AppException(RefundError.INVALID_STATUS)

        if refund.refund_type != RefundType.RETURN_REFUND:
            raise AppException(RefundError.INVALID_STATUS, message="仅退货退款需要填运单号")

        refund.return_company = return_company
        refund.return_tracking_no = return_tracking_no
        refund.status = RefundStatus.RETURNING

        logger.info(
            "refund_return_shipped",
            refund_no=refund.refund_no,
            tracking=return_tracking_no,
        )

    # --------------------------------------------------------------------------
    # 4. 管理员确认收到退货 → 执行退款
    # --------------------------------------------------------------------------
    async def confirm_return(self, refund_id: UUID) -> None:
        """管理员确认收到退货，执行退款"""
        refund = await self.repo.get_by_id(refund_id)
        if not refund:
            raise AppException(RefundError.NOT_FOUND)

        if refund.status != RefundStatus.RETURNING:
            raise AppException(RefundError.INVALID_STATUS)

        await self._execute_refund(refund)

        logger.info("refund_return_confirmed", refund_no=refund.refund_no)

    # --------------------------------------------------------------------------
    # 退款执行引擎（内部）
    # --------------------------------------------------------------------------
    async def _execute_refund(self, refund: RefundRecord) -> None:
        """
        执行退款原子操作：退钱 + 扣回佣金 + 恢复库存 + 订单状态变更

        退款路径：
        - 余额支付 → 退回到余额
        - 微信支付 → 调用微信退款（或余额补偿）
        """
        from app.domains.orders.commission_service import CommissionService
        from app.domains.payments.service import PaymentService
        from app.domains.products.repository import ProductRepository, ProductSkuRepository

        now_iso = datetime.now(timezone.utc).isoformat()

        order = await self.order_repo.get_by_id(refund.order_id)
        if not order:
            raise AppException(RefundError.ORDER_NOT_FOUND)

        # 1. 执行退款
        payment_svc = PaymentService(self.db)
        await payment_svc.refund_payment(order.id)

        # 2. 扣回佣金（如有冻结佣金）
        commission_svc = CommissionService(self.db)
        await commission_svc.revoke_commissions(order)

        # 3. 恢复库存（仅未发货状态恢复）
        if order.status == OrderStatus.PENDING_SHIPMENT:
            product_repo = ProductRepository(self.db)
            sku_repo = ProductSkuRepository(self.db)
            items = await self.order_repo.get_items(order.id)
            for item in items:
                if item.sku_id:
                    await sku_repo.restore_stock(item.sku_id, item.quantity)
                else:
                    await product_repo.restore_stock(item.product_id, item.quantity)

        # 4. 更新退款记录状态
        refund.status = RefundStatus.REFUNDED
        refund.refunded_at = now_iso

        # 5. 更新订单状态
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = now_iso
        order.cancel_reason = f"售后退款: {refund.reason}"
        order.commission_total = Decimal("0.00")

        logger.info(
            "refund_executed",
            refund_no=refund.refund_no,
            order_no=order.order_no,
            amount=str(refund.refund_amount),
        )
