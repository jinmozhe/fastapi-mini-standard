"""
File: app/domains/user_wallets/router.py
Description: 用户钱包双端路由

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app.api.deps import CurrentAdmin, CurrentUser
from app.core.response import ResponseModel
from app.core.exceptions import AppException
from app.db.models.user_wallet import UserBalanceLog, UserPointLog
from app.domains.user_wallets.constants import BalanceChangeType, PointChangeType, WalletError
from app.domains.user_wallets.dependencies import WalletServiceDep
from app.domains.user_wallets.schemas import (
    AdminChangeBalanceReq,
    AdminChangePointsReq,
    BalanceLogRead,
    PointLogRead,
    UserWalletRead,
)

# C端（买家）路由器
wallet_router = APIRouter()

# B端（管理员）路由器
wallet_admin = APIRouter()


# ==============================================================================
# C端操作接口
# ==============================================================================


@wallet_router.get(
    "/me",
    response_model=ResponseModel[UserWalletRead],
    summary="查询我的钱包总览",
    description="自动创建空钱包并返回可用余额、冻结资金、总积分",
)
async def get_my_wallet(
    request: Request, user: CurrentUser, service: WalletServiceDep
) -> ResponseModel[Any]:
    wallet = await service.get_or_create_wallet(user.id)
    return ResponseModel.success(data=wallet)


@wallet_router.get(
    "/me/balance-logs",
    response_model=ResponseModel[list[BalanceLogRead]],
    summary="查询我的资金流水",
)
async def get_my_balance_logs(
    request: Request,
    user: CurrentUser,
    service: WalletServiceDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> ResponseModel[Any]:
    stmt = (
        select(UserBalanceLog)
        .where(UserBalanceLog.user_id == user.id)
        .order_by(UserBalanceLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    results = await service.db.scalars(stmt)
    return ResponseModel.success(data=list(results.all()))


@wallet_router.get(
    "/me/point-logs",
    response_model=ResponseModel[list[PointLogRead]],
    summary="查询我的积分流水",
)
async def get_my_point_logs(
    request: Request,
    user: CurrentUser,
    service: WalletServiceDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> ResponseModel[Any]:
    stmt = (
        select(UserPointLog)
        .where(UserPointLog.user_id == user.id)
        .order_by(UserPointLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    results = await service.db.scalars(stmt)
    return ResponseModel.success(data=list(results.all()))


# ==============================================================================
# B端后台管理操作接口
# ==============================================================================


@wallet_admin.get(
    "",
    response_model=ResponseModel[list[UserWalletRead]],
    summary="（后台）全站资金看板",
)
async def check_wallets(
    request: Request,
    admin: CurrentAdmin,
    service: WalletServiceDep,
    user_id: UUID | None = Query(default=None, description="按指定用户筛选"),
    skip: int = 0,
    limit: int = 20,
) -> ResponseModel[Any]:
    """查询用户钱包，可以定位异常"""
    stmt = select(service.wallet_repo.model)
    if user_id:
        stmt = stmt.where(service.wallet_repo.model.user_id == user_id)
    stmt = stmt.offset(skip).limit(limit)
    res = await service.db.scalars(stmt)
    return ResponseModel.success(data=list(res.all()))


@wallet_admin.post(
    "/{user_id}/balance/grant",
    response_model=ResponseModel[UserWalletRead],
    summary="（后台）手工充值资金",
)
async def admin_grant_balance(
    request: Request,
    user_id: UUID,
    payload: AdminChangeBalanceReq,
    admin: CurrentAdmin,
    service: WalletServiceDep,
) -> ResponseModel[Any]:
    wallet = await service.change_balance(
        user_id=user_id,
        amount_delta=payload.amount,
        change_type=BalanceChangeType.ADMIN_RECHARGE,
        remark=payload.remark,
    )
    return ResponseModel.success(data=wallet)


@wallet_admin.post(
    "/{user_id}/balance/deduct",
    response_model=ResponseModel[UserWalletRead],
    summary="（后台）手工扣减资金",
)
async def admin_deduct_balance(
    request: Request,
    user_id: UUID,
    payload: AdminChangeBalanceReq,
    admin: CurrentAdmin,
    service: WalletServiceDep,
) -> ResponseModel[Any]:
    # 金额必须取反
    wallet = await service.change_balance(
        user_id=user_id,
        amount_delta=-payload.amount,
        change_type=BalanceChangeType.ADMIN_DEDUCT,
        remark=payload.remark,
    )
    return ResponseModel.success(data=wallet)


@wallet_admin.post(
    "/{user_id}/points/grant",
    response_model=ResponseModel[UserWalletRead],
    summary="（后台）给用户派发积分",
)
async def admin_grant_points(
    request: Request,
    user_id: UUID,
    payload: AdminChangePointsReq,
    admin: CurrentAdmin,
    service: WalletServiceDep,
) -> ResponseModel[Any]:
    wallet = await service.change_points(
        user_id=user_id,
        points_delta=payload.points,
        change_type=PointChangeType.ADMIN_GRANT,
        remark=payload.remark,
    )
    return ResponseModel.success(data=wallet)


@wallet_admin.post(
    "/{user_id}/points/deduct",
    response_model=ResponseModel[UserWalletRead],
    summary="（后台）手工扣减积分",
)
async def admin_deduct_points(
    request: Request,
    user_id: UUID,
    payload: AdminChangePointsReq,
    admin: CurrentAdmin,
    service: WalletServiceDep,
) -> ResponseModel[Any]:
    wallet = await service.change_points(
        user_id=user_id,
        points_delta=-payload.points,
        change_type=PointChangeType.ADMIN_REVOKE,
        remark=payload.remark,
    )
    return ResponseModel.success(data=wallet)


@wallet_admin.get(
    "/balance-logs",
    response_model=ResponseModel[list[BalanceLogRead]],
    summary="（后台）全站资金明细表审计",
)
async def admin_get_balance_logs(
    request: Request,
    admin: CurrentAdmin,
    service: WalletServiceDep,
    user_id: UUID | None = Query(default=None, description="筛查指定用户"),
    change_type: BalanceChangeType | None = Query(default=None, description="变动类型"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> ResponseModel[Any]:
    stmt = select(UserBalanceLog)
    if user_id:
        stmt = stmt.where(UserBalanceLog.user_id == user_id)
    if change_type:
        stmt = stmt.where(UserBalanceLog.change_type == change_type)
    
    stmt = stmt.order_by(UserBalanceLog.created_at.desc()).offset(skip).limit(limit)
    res = await service.db.scalars(stmt)
    return ResponseModel.success(data=list(res.all()))


@wallet_admin.get(
    "/point-logs",
    response_model=ResponseModel[list[PointLogRead]],
    summary="（后台）全站积分明细表审计",
)
async def admin_get_point_logs(
    request: Request,
    admin: CurrentAdmin,
    service: WalletServiceDep,
    user_id: UUID | None = Query(default=None, description="筛查指定用户"),
    change_type: PointChangeType | None = Query(default=None, description="变动类型"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> ResponseModel[Any]:
    stmt = select(UserPointLog)
    if user_id:
        stmt = stmt.where(UserPointLog.user_id == user_id)
    if change_type:
        stmt = stmt.where(UserPointLog.change_type == change_type)
        
    stmt = stmt.order_by(UserPointLog.created_at.desc()).offset(skip).limit(limit)
    res = await service.db.scalars(stmt)
    return ResponseModel.success(data=list(res.all()))
