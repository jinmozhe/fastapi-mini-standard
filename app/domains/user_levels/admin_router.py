"""
File: app/domains/user_levels/admin_router.py
Description: 用户等级领域 B端管理路由 (user_levels_admin)

定义 B 端管理员维护等级配置的 API 端点：
  GET    /api/v1/admin/user_levels          → 获取所有等级列表
  POST   /api/v1/admin/user_levels          → 创建新等级
  PUT    /api/v1/admin/user_levels/{id}     → 修改等级配置
  DELETE /api/v1/admin/user_levels/{id}     → 删除等级
  POST   /api/v1/admin/user_levels/users/{user_id}/override  → 强制指定用户等级
  POST   /api/v1/admin/user_levels/users/{user_id}/release   → 解除人工锁定

Author: jinmozhe
Created: 2026-04-12
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentAdmin, DBSession
from app.core.response import ResponseModel
from app.domains.user_levels.constants import UserLevelMsg
from app.domains.user_levels.repository import (
    UserLevelProfileRepository,
    UserLevelRecordRepository,
    UserLevelRepository,
)
from app.domains.user_levels.schemas import (
    UserLevelCreateRequest,
    UserLevelOut,
    UserLevelOverrideRequest,
    UserLevelUpdateRequest,
)
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
# B端路由定义
# ------------------------------------------------------------------------------


@router.get(
    "/",
    response_model=ResponseModel[list[UserLevelOut]],
    summary="获取所有等级列表",
    description="获取所有会员等级 (含停用)，B端后台管理界面使用。",
)
async def admin_list_levels(
    admin: CurrentAdmin,
    service: LevelServiceDep,
) -> ResponseModel[list[UserLevelOut]]:
    """获取等级列表 (B端完整版，含分佣/奖励规则)"""
    levels = await service.get_all_levels()
    data = [UserLevelOut.model_validate(lvl) for lvl in levels]
    return ResponseModel.success(data=data, message=UserLevelMsg.LEVEL_LIST)


@router.post(
    "/",
    response_model=ResponseModel[UserLevelOut],
    summary="创建会员等级",
    description=(
        "创建新的会员等级配置。\\n\\n"
        "**upgrade_rules** 支持 JSONB AST 规则树：\\n"
        '`{"op":"AND","conditions":[{"metric":"total_consume","operator":">=","value":10000}]}`'
    ),
)
async def admin_create_level(
    body: UserLevelCreateRequest,
    admin: CurrentAdmin,
    service: LevelServiceDep,
) -> ResponseModel[UserLevelOut]:
    """创建等级"""
    level = await service.create_level(**body.model_dump())
    data = UserLevelOut.model_validate(level)
    return ResponseModel.success(data=data, message=UserLevelMsg.LEVEL_CREATED)


@router.put(
    "/{level_id}",
    response_model=ResponseModel[UserLevelOut],
    summary="修改等级配置",
    description="修改会员等级的名称、折扣率、升级规则、分佣规则等。仅传递需要修改的字段。",
)
async def admin_update_level(
    level_id: uuid.UUID,
    body: UserLevelUpdateRequest,
    admin: CurrentAdmin,
    service: LevelServiceDep,
) -> ResponseModel[UserLevelOut]:
    """更新等级"""
    level = await service.update_level(
        level_id, **body.model_dump(exclude_unset=True)
    )
    data = UserLevelOut.model_validate(level)
    return ResponseModel.success(data=data, message=UserLevelMsg.LEVEL_UPDATED)


@router.delete(
    "/{level_id}",
    response_model=ResponseModel[None],
    summary="删除等级",
    description="删除会员等级。若该等级下存在关联用户，将阻断删除并返回错误。",
)
async def admin_delete_level(
    level_id: uuid.UUID,
    admin: CurrentAdmin,
    service: LevelServiceDep,
) -> ResponseModel[None]:
    """删除等级"""
    await service.delete_level(level_id)
    return ResponseModel.success(data=None, message=UserLevelMsg.LEVEL_DELETED)


@router.post(
    "/users/{user_id}/override",
    response_model=ResponseModel[None],
    summary="强制指定用户等级",
    description=(
        "后台管理员强制将某用户锁定到指定等级。\\n\\n"
        "设置后该用户的 `is_manual=true`，系统自动升降级程序将跳过此用户。"
    ),
)
async def admin_override_user_level(
    user_id: uuid.UUID,
    body: UserLevelOverrideRequest,
    admin: CurrentAdmin,
    service: LevelServiceDep,
) -> ResponseModel[None]:
    """人工强制指定用户等级"""
    await service.override_user_level(
        user_id=user_id, level_id=body.level_id, remark=body.remark
    )
    return ResponseModel.success(data=None, message=UserLevelMsg.OVERRIDE_SUCCESS)


@router.post(
    "/users/{user_id}/release",
    response_model=ResponseModel[None],
    summary="解除人工锁定",
    description="解除用户的人工等级锁定，让系统恢复自动计算升降级。",
)
async def admin_release_user_level(
    user_id: uuid.UUID,
    admin: CurrentAdmin,
    service: LevelServiceDep,
) -> ResponseModel[None]:
    """解除人工等级锁定"""
    await service.release_manual_lock(user_id=user_id)
    return ResponseModel.success(data=None, message=UserLevelMsg.RELEASE_SUCCESS)
