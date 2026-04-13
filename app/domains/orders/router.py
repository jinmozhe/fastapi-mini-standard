"""
File: app/domains/orders/router.py
Description: 订单 C 端路由

接口：
- POST /checkout/preview   → 结算预览
- POST /                   → 提交订单
- POST /{id}/pay           → 去支付
- GET  /                   → 我的订单列表
- GET  /{id}               → 订单详情
- PATCH /{id}/cancel       → 取消订单（仅待付款）
- PATCH /{id}/confirm      → 确认收货

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentUser, DBSession
from app.core.response import ResponseModel
from app.domains.orders.dependencies import OrderServiceDep
from app.domains.orders.repository import CommissionRepository, OrderRepository
from app.domains.orders.schemas import (
    CheckoutPreviewReq,
    CheckoutPreviewResult,
    CommissionRecordRead,
    OrderCreateReq,
    OrderCreateResult,
    OrderDetailRead,
    OrderItemRead,
    OrderListItem,
    OrderPageResult,
    OrderPayReq,
)

order_router = APIRouter()


# ==============================================================================
# 结算预览
# ==============================================================================

@order_router.post(
    "/checkout/preview",
    response_model=ResponseModel[CheckoutPreviewResult],
    summary="结算预览",
)
async def checkout_preview(
    request: Request,
    body: CheckoutPreviewReq,
    user: CurrentUser,
    service: OrderServiceDep,
) -> ResponseModel[Any]:
    """计算实时价格 + 运费，不创建订单"""
    result = await service.checkout_preview(user.id, body)
    await service.db.commit()
    return ResponseModel.success(data=result)


# ==============================================================================
# 提交订单
# ==============================================================================

@order_router.post(
    "/",
    response_model=ResponseModel[OrderCreateResult],
    summary="提交订单",
)
async def create_order(
    request: Request,
    body: OrderCreateReq,
    user: CurrentUser,
    service: OrderServiceDep,
) -> ResponseModel[Any]:
    """锁库存 + 快照 + 创建订单（不支付）"""
    result = await service.create_order(user.id, body)
    await service.db.commit()
    return ResponseModel.success(data=result)


# ==============================================================================
# 去支付
# ==============================================================================

@order_router.post(
    "/{order_id}/pay",
    summary="去支付",
)
async def pay_order(
    request: Request,
    order_id: UUID,
    body: OrderPayReq,
    user: CurrentUser,
    service: OrderServiceDep,
) -> ResponseModel[Any]:
    """选择支付方式，发起支付"""
    result = await service.pay_order(user.id, order_id, body)
    await service.db.commit()
    return ResponseModel.success(data=result)


# ==============================================================================
# 我的订单列表
# ==============================================================================

@order_router.get(
    "/",
    response_model=ResponseModel[OrderPageResult],
    summary="我的订单列表",
)
async def list_my_orders(
    request: Request,
    user: CurrentUser,
    service: OrderServiceDep,
    status: str | None = Query(default=None, description="按状态筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> ResponseModel[Any]:
    """分页查询我的订单"""
    repo = service.repo
    orders, total = await repo.list_by_user(user.id, status, page, page_size)

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
# 订单详情
# ==============================================================================

@order_router.get(
    "/{order_id}",
    response_model=ResponseModel[OrderDetailRead],
    summary="订单详情",
)
async def get_order_detail(
    request: Request,
    order_id: UUID,
    user: CurrentUser,
    service: OrderServiceDep,
) -> ResponseModel[Any]:
    """获取订单详情（含明细 + 佣金）"""
    from app.core.exceptions import AppException
    from app.domains.orders.constants import OrderError

    order = await service.repo.get_by_id(order_id)
    if not order or order.user_id != user.id:
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
# 取消订单（仅待付款）
# ==============================================================================

@order_router.patch(
    "/{order_id}/cancel",
    summary="取消订单",
)
async def cancel_order(
    request: Request,
    order_id: UUID,
    user: CurrentUser,
    service: OrderServiceDep,
) -> ResponseModel[Any]:
    """用户自助取消（仅 pending_payment 状态）"""
    await service.cancel_order(user.id, order_id)
    await service.db.commit()
    return ResponseModel.success(message="订单已取消")


# ==============================================================================
# 确认收货
# ==============================================================================

@order_router.patch(
    "/{order_id}/confirm",
    summary="确认收货",
)
async def confirm_order(
    request: Request,
    order_id: UUID,
    user: CurrentUser,
    service: OrderServiceDep,
) -> ResponseModel[Any]:
    """买家确认收货"""
    await service.confirm_order(user.id, order_id)
    await service.db.commit()
    return ResponseModel.success(message="确认收货成功")
