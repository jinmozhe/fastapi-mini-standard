"""
File: app/domains/user_levels/router.py
Description: 用户等级领域 C端路由 (user_levels_router)

定义 C 端用户可访问的等级体系接口：
  GET /api/v1/user_levels  → 获取全站会员等级体系 (脱敏展示)

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DBSession
from app.core.response import ResponseModel
from app.domains.user_levels.constants import UserLevelMsg
from app.domains.user_levels.repository import (
    UserLevelProfileRepository,
    UserLevelRecordRepository,
    UserLevelRepository,
)
from app.domains.user_levels.schemas import UserLevelProfileOut, UserLevelPublicOut
from app.domains.user_levels.service import UserLevelService

router = APIRouter()


# ------------------------------------------------------------------------------
# 依赖注入构造器
# ------------------------------------------------------------------------------


async def get_level_service(session: DBSession) -> UserLevelService:
    """构建 UserLevelService 实例"""
    return UserLevelService(
        level_repo=UserLevelRepository(session=session),
        profile_repo=UserLevelProfileRepository(session=session),
        record_repo=UserLevelRecordRepository(session=session),
    )


LevelServiceDep = Annotated[UserLevelService, Depends(get_level_service)]


# ------------------------------------------------------------------------------
# C端路由定义
# ------------------------------------------------------------------------------


@router.get(
    "/",
    response_model=ResponseModel[list[UserLevelPublicOut]],
    summary="获取会员等级体系",
    description=(
        "返回当前启用的所有会员等级的公开信息。\\n\\n"
        "用于前端展示 VIP 体系说明页、等级权益对比表等。\\n\\n"
        "**注意**：分佣规则和奖励规则等 B端敏感配置已脱敏，不会暴露给 C端。"
    ),
)
async def get_level_list(
    service: LevelServiceDep,
) -> ResponseModel[list[UserLevelPublicOut]]:
    """获取全站会员等级列表 (C端脱敏版)"""
    levels = await service.get_active_levels()
    data = [UserLevelPublicOut.model_validate(lvl) for lvl in levels]
    return ResponseModel.success(data=data, message=UserLevelMsg.C_LEVEL_LIST)


@router.get(
    "/me",
    response_model=ResponseModel[UserLevelProfileOut],
    summary="获取我的等级与进度",
    description="获取当前登录用户的身份等级信息、各项历史累计指标（总消费、邀请人数等），用于前端展示用户等级中心。",
)
async def get_my_level_profile(
    current_user: CurrentUser,
    service: LevelServiceDep,
) -> ResponseModel[UserLevelProfileOut]:
    """获取当前用户的等级档案与进度"""
    data = await service.get_user_profile_detail(current_user.id)
    out_data = UserLevelProfileOut.model_validate(data)
    return ResponseModel.success(data=out_data)
