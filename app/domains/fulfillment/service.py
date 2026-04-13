"""
File: app/domains/fulfillment/service.py
Description: 履约核心业务逻辑

从 orders/service.py 迁入的方法：
- ship_order()     → 单个发货
- confirm_order()  → 买家确认收货

新增方法：
- batch_ship()     → 批量发货
- auto_confirm()   → 自动确认收货（定时任务调用）

Author: jinmozhe
Created: 2026-04-13
"""

from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import logger
from app.db.models.order import Order
from app.domains.fulfillment.constants import AUTO_CONFIRM_DAYS, FulfillmentError
from app.domains.fulfillment.schemas import (
    BatchShipItem,
    BatchShipResult,
    BatchShipResultItem,
    AutoConfirmResult,
)
from app.domains.orders.commission_service import CommissionService
from app.domains.orders.constants import OrderStatus
from app.domains.orders.repository import OrderRepository


class FulfillmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.order_repo = OrderRepository(db)
        self.commission_service = CommissionService(db)

    # --------------------------------------------------------------------------
    # 单个发货（从 orders 迁入）
    # --------------------------------------------------------------------------
    async def ship_order(
        self,
        order_id: UUID,
        shipping_company: str,
        tracking_number: str,
    ) -> None:
        """管理员发货"""
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise AppException(FulfillmentError.ORDER_NOT_FOUND)

        if order.status != OrderStatus.PENDING_SHIPMENT:
            raise AppException(FulfillmentError.CANNOT_SHIP)

        now_iso = datetime.now(timezone.utc).isoformat()
        order.status = OrderStatus.SHIPPED
        order.shipping_company = shipping_company
        order.tracking_number = tracking_number
        order.shipped_at = now_iso

        logger.info(
            "order_shipped",
            order_no=order.order_no,
            tracking=tracking_number,
        )

    # --------------------------------------------------------------------------
    # 批量发货
    # --------------------------------------------------------------------------
    async def batch_ship(self, items: list[BatchShipItem]) -> BatchShipResult:
        """批量发货：逐条处理，部分失败不影响其他"""
        results: list[BatchShipResultItem] = []
        success_count = 0

        for item in items:
            try:
                await self.ship_order(
                    order_id=item.order_id,
                    shipping_company=item.shipping_company,
                    tracking_number=item.tracking_number,
                )
                results.append(BatchShipResultItem(
                    order_id=item.order_id, success=True, message="发货成功"
                ))
                success_count += 1
            except AppException as e:
                results.append(BatchShipResultItem(
                    order_id=item.order_id, success=False, message=e.message
                ))
            except Exception as e:
                results.append(BatchShipResultItem(
                    order_id=item.order_id, success=False, message=str(e)
                ))

        return BatchShipResult(
            total=len(items),
            success_count=success_count,
            fail_count=len(items) - success_count,
            details=results,
        )

    # --------------------------------------------------------------------------
    # 买家确认收货（从 orders 迁入）
    # --------------------------------------------------------------------------
    async def confirm_order(self, user_id: UUID, order_id: UUID) -> None:
        """买家手动确认收货"""
        order = await self.order_repo.get_by_id(order_id)
        if not order or order.user_id != user_id:
            raise AppException(FulfillmentError.ORDER_NOT_FOUND)

        if order.status != OrderStatus.SHIPPED:
            raise AppException(FulfillmentError.CANNOT_CONFIRM)

        await self._do_confirm(order)

    # --------------------------------------------------------------------------
    # 自动确认收货（定时任务调用）
    # --------------------------------------------------------------------------
    async def auto_confirm(self) -> AutoConfirmResult:
        """
        自动确认收货引擎。

        查询所有 shipped 状态且 shipped_at 超过 AUTO_CONFIRM_DAYS 的订单，
        逐条执行确认收货 + 佣金释放。

        供定时任务（Celery/APScheduler/cron 脚本）调用。
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=AUTO_CONFIRM_DAYS)
        cutoff_iso = cutoff.isoformat()

        # 查询需要自动确认的订单
        stmt = (
            select(Order)
            .where(
                Order.status == OrderStatus.SHIPPED,
                Order.shipped_at <= cutoff_iso,
                Order.is_deleted.is_(False),
            )
        )
        result = await self.db.scalars(stmt)
        orders = list(result.all())

        confirmed_nos: list[str] = []
        for order in orders:
            try:
                await self._do_confirm(order)
                confirmed_nos.append(order.order_no)
            except Exception as e:
                logger.error(
                    "auto_confirm_failed",
                    order_no=order.order_no,
                    error=str(e),
                )

        logger.info(
            "auto_confirm_completed",
            confirmed_count=len(confirmed_nos),
        )

        return AutoConfirmResult(
            confirmed_count=len(confirmed_nos),
            order_nos=confirmed_nos,
        )

    # --------------------------------------------------------------------------
    # 确认收货的公共逻辑
    # --------------------------------------------------------------------------
    async def _do_confirm(self, order: Order) -> None:
        """执行确认收货：状态变更 + 佣金释放"""
        now_iso = datetime.now(timezone.utc).isoformat()
        order.status = OrderStatus.COMPLETED
        order.completed_at = now_iso

        # 释放冻结佣金（payment 模式）或计算佣金（completion 模式）
        await self.commission_service.release_commissions(order)

        logger.info("order_completed", order_no=order.order_no)
