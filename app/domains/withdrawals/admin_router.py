"""
File: app/domains/withdrawals/admin_router.py
Description: 提现 B 端管理路由

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.core.response import ResponseModel
from app.domains.withdrawals.dependencies import WithdrawalServiceDep
from app.domains.withdrawals.schemas import (
    WithdrawalDetailRead,
    WithdrawalListItem,
    WithdrawalPageResult,
    WithdrawalReviewReq,
)

withdrawal_admin = APIRouter()


@withdrawal_admin.get(
    "/",
    response_model=ResponseModel[WithdrawalPageResult],
    summary="B端提现列表",
)
async def admin_list_withdrawals(
    request: Request,
    service: WithdrawalServiceDep,
    status: str | None = Query(default=None, description="按状态筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> ResponseModel[Any]:
    """全量提现列表"""
    rows, total = await service.repo.list_all(status, page, page_size)
    items = [WithdrawalListItem.model_validate(r) for r in rows]
    return ResponseModel.success(data=WithdrawalPageResult(
        items=items, total=total, page=page, page_size=page_size,
    ))


@withdrawal_admin.get(
    "/{withdrawal_id}",
    response_model=ResponseModel[WithdrawalDetailRead],
    summary="B端提现详情",
)
async def admin_withdrawal_detail(
    request: Request,
    withdrawal_id: UUID,
    service: WithdrawalServiceDep,
) -> ResponseModel[Any]:
    """查看提现详情"""
    from app.core.exceptions import AppException
    from app.domains.withdrawals.constants import WithdrawalError

    record = await service.repo.get_by_id(withdrawal_id)
    if not record:
        raise AppException(WithdrawalError.NOT_FOUND)
    return ResponseModel.success(data=WithdrawalDetailRead.model_validate(record))


@withdrawal_admin.patch(
    "/{withdrawal_id}/review",
    summary="审核提现",
)
async def admin_review_withdrawal(
    request: Request,
    withdrawal_id: UUID,
    body: WithdrawalReviewReq,
    service: WithdrawalServiceDep,
) -> ResponseModel[Any]:
    """审核提现申请：通过或驳回"""
    await service.review_withdrawal(withdrawal_id, body.action, admin_remark=body.admin_remark)
    await service.db.commit()
    return ResponseModel.success(message="审核完成")


@withdrawal_admin.patch(
    "/{withdrawal_id}/complete",
    summary="确认打款完成",
)
async def admin_complete_withdrawal(
    request: Request,
    withdrawal_id: UUID,
    service: WithdrawalServiceDep,
) -> ResponseModel[Any]:
    """确认已打款完成"""
    await service.complete_withdrawal(withdrawal_id)
    await service.db.commit()
    return ResponseModel.success(message="打款确认完成")
