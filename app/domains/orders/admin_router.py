"""
File: app/domains/orders/admin_router.py
Description: 订单 B 端管理路由

接口：
- GET   /                 → 订单列表
- GET   /{id}             → 订单详情
- PATCH /{id}/ship        → 发货
- PATCH /{id}/force-cancel → 强制取消（退款+扣回佣金）

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentUser
from app.core.response import ResponseModel
from app.domains.orders.dependencies import OrderServiceDep
from app.domains.orders.repository import CommissionRepository
from app.domains.orders.schemas import (
    CommissionRecordRead,
    OrderDetailRead,
    OrderForceCancelReq,
    OrderItemRead,
    OrderListItem,
    OrderPageResult,
    OrderShipReq,
)

order_admin = APIRouter()


# ==============================================================================
# B 端订单列表
# ==============================================================================

@order_admin.get(
    "/",
    response_model=ResponseModel[OrderPageResult],
    summary="B端订单列表",
)
async def admin_list_orders(
    request: Request,
    service: OrderServiceDep,
    status: str | None = Query(default=None, description="按状态筛选"),
    user_id: UUID | None = Query(default=None, description="按用户筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> ResponseModel[Any]:
    """B 端全量订单列表"""
    repo = service.repo
    orders, total = await repo.list_all(status, user_id, page, page_size)

    items = []
    for o in orders:
        item_count = await repo.count_items(o.id)
        first_item = await repo.get_first_item(o.id)
        items.append(OrderListItem(
            id=o.id,
            order_no=o.order_no,
            status=o.status,
            items_amount=o.items_amount,
            freight_amount=o.freight_amount,
            total_amount=o.total_amount,
            commission_total=o.commission_total,
            payment_method=o.payment_method,
            item_count=item_count,
            first_item_snapshot=first_item.product_snapshot if first_item else None,
            created_at=o.created_at,
        ))

    return ResponseModel.success(data=OrderPageResult(
        items=items, total=total, page=page, page_size=page_size,
    ))


# ==============================================================================
# B 端订单详情
# ==============================================================================

@order_admin.get(
    "/{order_id}",
    response_model=ResponseModel[OrderDetailRead],
    summary="B端订单详情",
)
async def admin_order_detail(
    request: Request,
    order_id: UUID,
    service: OrderServiceDep,
) -> ResponseModel[Any]:
    """B 端订单详情（含全量佣金明细）"""
    from app.core.exceptions import AppException
    from app.domains.orders.constants import OrderError

    order = await service.repo.get_by_id(order_id)
    if not order:
        raise AppException(OrderError.NOT_FOUND)

    items = await service.repo.get_items(order_id)
    comm_repo = CommissionRepository(service.db)
    commissions = await comm_repo.get_by_order(order_id)

    detail = OrderDetailRead(
        id=order.id,
        order_no=order.order_no,
        user_id=order.user_id,
        status=order.status,
        address_snapshot=order.address_snapshot,
        items_amount=order.items_amount,
        freight_amount=order.freight_amount,
        total_amount=order.total_amount,
        commission_total=order.commission_total,
        payment_method=order.payment_method,
        paid_at=order.paid_at,
        shipping_company=order.shipping_company,
        tracking_number=order.tracking_number,
        shipped_at=order.shipped_at,
        completed_at=order.completed_at,
        cancelled_at=order.cancelled_at,
        cancel_reason=order.cancel_reason,
        remark=order.remark,
        items=[OrderItemRead.model_validate(i) for i in items],
        commissions=[CommissionRecordRead.model_validate(c) for c in commissions],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )
    return ResponseModel.success(data=detail)


# ==============================================================================
# 发货
# ==============================================================================

@order_admin.patch(
    "/{order_id}/ship",
    summary="发货",
)
async def admin_ship_order(
    request: Request,
    order_id: UUID,
    body: OrderShipReq,
    service: OrderServiceDep,
) -> ResponseModel[Any]:
    """填写快递公司和运单号，发货"""
    await service.ship_order(order_id, body.shipping_company, body.tracking_number)
    await service.db.commit()
    return ResponseModel.success(message="发货成功")


# ==============================================================================
# 强制取消（退款+扣回佣金）
# ==============================================================================

@order_admin.patch(
    "/{order_id}/force-cancel",
    summary="强制取消订单",
)
async def admin_force_cancel(
    request: Request,
    order_id: UUID,
    body: OrderForceCancelReq,
    user: CurrentUser,
    service: OrderServiceDep,
) -> ResponseModel[Any]:
    """管理员强制取消：退款 + 扣回佣金 + 释放库存"""
    await service.force_cancel(order_id, user.id, body.cancel_reason)
    await service.db.commit()
    return ResponseModel.success(message="订单已强制取消，退款和佣金扣回已完成")
