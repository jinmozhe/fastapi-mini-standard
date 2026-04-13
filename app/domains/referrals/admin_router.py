"""
File: app/domains/referrals/admin_router.py
Description: 推荐关系 B 端管理路由

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request

from app.core.response import ResponseModel
from app.domains.referrals.dependencies import ReferralServiceDep
from app.domains.referrals.schemas import (
    AdminBindReq,
    AdminTeamResult,
    TeamMemberItem,
)

referral_admin = APIRouter()


@referral_admin.get(
    "/{user_id}/team",
    response_model=ResponseModel[AdminTeamResult],
    summary="查看用户团队树",
)
async def admin_get_team(
    request: Request,
    user_id: UUID,
    service: ReferralServiceDep,
) -> ResponseModel[Any]:
    """管理员查看任意用户的三级团队"""
    from app.core.exceptions import AppException
    from app.domains.referrals.constants import ReferralError

    user = await service.repo.get_user(user_id)
    if not user:
        raise AppException(ReferralError.USER_NOT_FOUND)

    first_members, _ = await service.get_team_members(user_id, level=1, page=1, page_size=100)
    second_members, _ = await service.get_team_members(user_id, level=2, page=1, page_size=100)
    third_members, _ = await service.get_team_members(user_id, level=3, page=1, page_size=100)
    stats = await service.get_team_stats(user_id)

    return ResponseModel.success(data=AdminTeamResult(
        user_id=user_id,
        nickname=user.nickname,
        first_level=first_members,
        second_level=second_members,
        third_level=third_members,
        stats=stats,
    ))


@referral_admin.post(
    "/bind",
    summary="手动绑定推荐人",
)
async def admin_bind(
    request: Request,
    body: AdminBindReq,
    service: ReferralServiceDep,
) -> ResponseModel[Any]:
    """管理员手动建立推荐关系"""
    await service.admin_bind(body.user_id, body.inviter_id)
    await service.db.commit()
    return ResponseModel.success(message="绑定成功")


@referral_admin.delete(
    "/{user_id}/unbind",
    summary="解除推荐关系",
)
async def admin_unbind(
    request: Request,
    user_id: UUID,
    service: ReferralServiceDep,
) -> ResponseModel[Any]:
    """管理员解除推荐绑定"""
    await service.admin_unbind(user_id)
    await service.db.commit()
    return ResponseModel.success(message="解绑成功")
