"""
File: app/domains/refunds/admin_router.py
Description: 售后退款 B 端管理路由

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.core.response import ResponseModel
from app.domains.refunds.dependencies import RefundServiceDep
from app.domains.refunds.schemas import (
    RefundDetailRead,
    RefundListItem,
    RefundPageResult,
    RefundReviewReq,
)

refund_admin = APIRouter()


@refund_admin.get(
    "/",
    response_model=ResponseModel[RefundPageResult],
    summary="B端退款列表",
)
async def admin_list_refunds(
    request: Request,
    service: RefundServiceDep,
    status: str | None = Query(default=None, description="按状态筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> ResponseModel[Any]:
    """全量退款列表"""
    rows, total = await service.repo.list_all(status, page, page_size)
    items = [RefundListItem.model_validate(r) for r in rows]
    return ResponseModel.success(data=RefundPageResult(
        items=items, total=total, page=page, page_size=page_size,
    ))


@refund_admin.get(
    "/{refund_id}",
    response_model=ResponseModel[RefundDetailRead],
    summary="B端退款详情",
)
async def admin_refund_detail(
    request: Request,
    refund_id: UUID,
    service: RefundServiceDep,
) -> ResponseModel[Any]:
    """查看退款详情"""
    from app.core.exceptions import AppException
    from app.domains.refunds.constants import RefundError

    refund = await service.repo.get_by_id(refund_id)
    if not refund:
        raise AppException(RefundError.NOT_FOUND)
    return ResponseModel.success(data=RefundDetailRead.model_validate(refund))


@refund_admin.patch(
    "/{refund_id}/review",
    summary="审核退款",
)
async def admin_review_refund(
    request: Request,
    refund_id: UUID,
    body: RefundReviewReq,
    service: RefundServiceDep,
) -> ResponseModel[Any]:
    """审核退款申请：通过或驳回"""
    await service.review_refund(refund_id, body.action, body.admin_remark)
    await service.db.commit()
    return ResponseModel.success(message="审核完成")


@refund_admin.patch(
    "/{refund_id}/confirm-return",
    summary="确认收到退货",
)
async def admin_confirm_return(
    request: Request,
    refund_id: UUID,
    service: RefundServiceDep,
) -> ResponseModel[Any]:
    """确认收到退货，系统自动执行退款"""
    await service.confirm_return(refund_id)
    await service.db.commit()
    return ResponseModel.success(message="退货已确认，退款已完成")
