"""
File: app/domains/fulfillment/admin_router.py
Description: 履约 B 端管理路由

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request

from app.core.response import ResponseModel
from app.domains.fulfillment.dependencies import FulfillmentServiceDep
from app.domains.fulfillment.schemas import (
    AutoConfirmResult,
    BatchShipReq,
    BatchShipResult,
    ShipOrderReq,
)

fulfillment_admin = APIRouter()


@fulfillment_admin.patch(
    "/{order_id}/ship",
    summary="发货",
)
async def admin_ship_order(
    request: Request,
    order_id: UUID,
    body: ShipOrderReq,
    service: FulfillmentServiceDep,
) -> ResponseModel[Any]:
    """填写快递公司和运单号，发货"""
    await service.ship_order(order_id, body.shipping_company, body.tracking_number)
    await service.db.commit()
    return ResponseModel.success(message="发货成功")


@fulfillment_admin.post(
    "/batch-ship",
    response_model=ResponseModel[BatchShipResult],
    summary="批量发货",
)
async def admin_batch_ship(
    request: Request,
    body: BatchShipReq,
    service: FulfillmentServiceDep,
) -> ResponseModel[Any]:
    """批量发货，部分失败不影响其他"""
    result = await service.batch_ship(body.items)
    await service.db.commit()
    return ResponseModel.success(data=result)


@fulfillment_admin.post(
    "/auto-confirm",
    response_model=ResponseModel[AutoConfirmResult],
    summary="触发自动确认收货",
)
async def admin_auto_confirm(
    request: Request,
    service: FulfillmentServiceDep,
) -> ResponseModel[Any]:
    """
    定时任务调用此接口，自动确认超时未操作的已发货订单。
    也可手动触发。
    """
    result = await service.auto_confirm()
    await service.db.commit()
    return ResponseModel.success(data=result)
