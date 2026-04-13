"""
File: app/domains/refunds/router.py
Description: 售后退款 C 端路由

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentUser
from app.core.response import ResponseModel
from app.domains.refunds.dependencies import RefundServiceDep
from app.domains.refunds.schemas import (
    RefundApplyReq,
    RefundApplyResult,
    RefundDetailRead,
    RefundListItem,
    RefundPageResult,
    ReturnShippingReq,
)

refund_router = APIRouter()


@refund_router.post(
    "/",
    response_model=ResponseModel[RefundApplyResult],
    summary="申请退款",
)
async def apply_refund(
    request: Request,
    body: RefundApplyReq,
    user: CurrentUser,
    service: RefundServiceDep,
) -> ResponseModel[Any]:
    """提交退款申请"""
    result = await service.apply_refund(user.id, body)
    await service.db.commit()
    return ResponseModel.success(data=result)


@refund_router.get(
    "/",
    response_model=ResponseModel[RefundPageResult],
    summary="我的退款",
)
async def list_my_refunds(
    request: Request,
    user: CurrentUser,
    service: RefundServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> ResponseModel[Any]:
    """分页查询我的退款记录"""
    rows, total = await service.repo.list_by_user(user.id, page, page_size)
    items = [RefundListItem.model_validate(r) for r in rows]
    return ResponseModel.success(data=RefundPageResult(
        items=items, total=total, page=page, page_size=page_size,
    ))


@refund_router.get(
    "/{refund_id}",
    response_model=ResponseModel[RefundDetailRead],
    summary="退款详情",
)
async def get_refund_detail(
    request: Request,
    refund_id: UUID,
    user: CurrentUser,
    service: RefundServiceDep,
) -> ResponseModel[Any]:
    """查看退款详情"""
    from app.core.exceptions import AppException
    from app.domains.refunds.constants import RefundError

    refund = await service.repo.get_by_id(refund_id)
    if not refund or refund.user_id != user.id:
        raise AppException(RefundError.NOT_FOUND)
    return ResponseModel.success(data=RefundDetailRead.model_validate(refund))


@refund_router.patch(
    "/{refund_id}/return-shipping",
    summary="填退货运单号",
)
async def submit_return_shipping(
    request: Request,
    refund_id: UUID,
    body: ReturnShippingReq,
    user: CurrentUser,
    service: RefundServiceDep,
) -> ResponseModel[Any]:
    """退货退款时填写退货运单号"""
    await service.submit_return_info(
        user.id, refund_id, body.return_company, body.return_tracking_no,
    )
    await service.db.commit()
    return ResponseModel.success(message="退货运单号已提交")
