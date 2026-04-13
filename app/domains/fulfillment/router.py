"""
File: app/domains/fulfillment/router.py
Description: 履约 C 端路由

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request

from app.api.deps import CurrentUser
from app.core.response import ResponseModel
from app.domains.fulfillment.dependencies import FulfillmentServiceDep

fulfillment_router = APIRouter()


@fulfillment_router.patch(
    "/{order_id}/confirm",
    summary="确认收货",
)
async def confirm_order(
    request: Request,
    order_id: UUID,
    user: CurrentUser,
    service: FulfillmentServiceDep,
) -> ResponseModel[Any]:
    """买家确认收货"""
    await service.confirm_order(user.id, order_id)
    await service.db.commit()
    return ResponseModel.success(message="确认收货成功")
