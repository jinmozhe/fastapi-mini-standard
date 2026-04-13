"""
File: app/domains/withdrawals/router.py
Description: 提现 C 端路由

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentUser
from app.core.response import ResponseModel
from app.domains.withdrawals.dependencies import WithdrawalServiceDep
from app.domains.withdrawals.schemas import (
    WithdrawApplyReq,
    WithdrawApplyResult,
    WithdrawalDetailRead,
    WithdrawalListItem,
    WithdrawalPageResult,
)

withdrawal_router = APIRouter()


@withdrawal_router.post(
    "/",
    response_model=ResponseModel[WithdrawApplyResult],
    summary="申请提现",
)
async def apply_withdrawal(
    request: Request,
    body: WithdrawApplyReq,
    user: CurrentUser,
    service: WithdrawalServiceDep,
) -> ResponseModel[Any]:
    """提交提现申请"""
    result = await service.apply_withdrawal(user.id, body)
    await service.db.commit()
    return ResponseModel.success(data=result)


@withdrawal_router.get(
    "/",
    response_model=ResponseModel[WithdrawalPageResult],
    summary="我的提现记录",
)
async def list_my_withdrawals(
    request: Request,
    user: CurrentUser,
    service: WithdrawalServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> ResponseModel[Any]:
    """分页查询我的提现记录"""
    rows, total = await service.repo.list_by_user(user.id, page, page_size)
    items = [WithdrawalListItem.model_validate(r) for r in rows]
    return ResponseModel.success(data=WithdrawalPageResult(
        items=items, total=total, page=page, page_size=page_size,
    ))


@withdrawal_router.get(
    "/{withdrawal_id}",
    response_model=ResponseModel[WithdrawalDetailRead],
    summary="提现详情",
)
async def get_withdrawal_detail(
    request: Request,
    withdrawal_id: UUID,
    user: CurrentUser,
    service: WithdrawalServiceDep,
) -> ResponseModel[Any]:
    """查看提现详情"""
    from app.core.exceptions import AppException
    from app.domains.withdrawals.constants import WithdrawalError

    record = await service.repo.get_by_id(withdrawal_id)
    if not record or record.user_id != user.id:
        raise AppException(WithdrawalError.NOT_FOUND)
    return ResponseModel.success(data=WithdrawalDetailRead.model_validate(record))
