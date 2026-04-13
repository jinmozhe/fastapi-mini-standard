"""
File: app/domains/referrals/router.py
Description: 推荐关系 C 端路由

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Any

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentUser
from app.core.response import ResponseModel
from app.domains.referrals.dependencies import ReferralServiceDep
from app.domains.referrals.schemas import (
    InviteCodeResult,
    InviterInfo,
    TeamMemberItem,
    TeamPageResult,
    TeamStats,
)

referral_router = APIRouter()


@referral_router.get(
    "/invite-code",
    response_model=ResponseModel[InviteCodeResult],
    summary="获取我的邀请码",
)
async def get_invite_code(
    request: Request,
    user: CurrentUser,
    service: ReferralServiceDep,
) -> ResponseModel[Any]:
    """首次请求自动生成邀请码"""
    result = await service.get_or_create_invite_code(user.id)
    await service.db.commit()
    return ResponseModel.success(data=result)


@referral_router.get(
    "/inviter",
    summary="我的推荐人",
)
async def get_my_inviter(
    request: Request,
    user: CurrentUser,
    service: ReferralServiceDep,
) -> ResponseModel[Any]:
    """查看谁邀请了我"""
    result = await service.get_inviter_info(user.id)
    return ResponseModel.success(data=result)


@referral_router.get(
    "/team/first",
    response_model=ResponseModel[TeamPageResult],
    summary="我的一级团队",
)
async def get_first_level_team(
    request: Request,
    user: CurrentUser,
    service: ReferralServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> ResponseModel[Any]:
    """我直接邀请的人"""
    items, total = await service.get_team_members(user.id, level=1, page=page, page_size=page_size)
    return ResponseModel.success(data=TeamPageResult(
        items=items, total=total, page=page, page_size=page_size,
    ))


@referral_router.get(
    "/team/second",
    response_model=ResponseModel[TeamPageResult],
    summary="我的二级团队",
)
async def get_second_level_team(
    request: Request,
    user: CurrentUser,
    service: ReferralServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> ResponseModel[Any]:
    """一级成员邀请的人"""
    items, total = await service.get_team_members(user.id, level=2, page=page, page_size=page_size)
    return ResponseModel.success(data=TeamPageResult(
        items=items, total=total, page=page, page_size=page_size,
    ))


@referral_router.get(
    "/team/third",
    response_model=ResponseModel[TeamPageResult],
    summary="我的三级团队",
)
async def get_third_level_team(
    request: Request,
    user: CurrentUser,
    service: ReferralServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> ResponseModel[Any]:
    """二级成员邀请的人"""
    items, total = await service.get_team_members(user.id, level=3, page=page, page_size=page_size)
    return ResponseModel.success(data=TeamPageResult(
        items=items, total=total, page=page, page_size=page_size,
    ))


@referral_router.get(
    "/team/stats",
    response_model=ResponseModel[TeamStats],
    summary="团队统计",
)
async def get_team_stats(
    request: Request,
    user: CurrentUser,
    service: ReferralServiceDep,
) -> ResponseModel[Any]:
    """一级/二级/三级人数与消费汇总"""
    result = await service.get_team_stats(user.id)
    return ResponseModel.success(data=result)
