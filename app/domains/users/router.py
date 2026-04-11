"""
File: app/domains/users/router.py
Description: 用户领域 HTTP 路由层

本模块定义了用户管理的 API 端点。
遵循规范：
1. 查询与更新接口 (GET/PATCH /me) 必须鉴权 (CurrentUser)
2. 删除接口 (DELETE /me) 必须鉴权，支持软删除
3. 注册接口已移到 auth 域 (POST /auth/register)

Author: jinmozhe
Created: 2025-12-05
Updated: 2026-04-03 (移除 create 到 auth 域，新增 delete)
"""

from fastapi import APIRouter, Request, status

from app.api.deps import CurrentUser
from app.core.response import ResponseModel

# 使用类型别名，代码极简
from app.domains.users.constants import UserMsg
from app.domains.users.dependencies import UserServiceDep
from app.domains.users.schemas import UserRead, UserUpdate

router = APIRouter()


# ------------------------------------------------------------------------------
# Protected Endpoints (受保护接口 - 需登录)
# ------------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=ResponseModel[UserRead],
    summary="获取我的个人资料",
    description="获取当前登录用户的详细信息。需携带有效 Token。",
)
async def read_user_me(
    request: Request,
    current_user: CurrentUser,  # ✅ 核心：通过 Token 自动注入当前用户对象
) -> ResponseModel[UserRead]:
    """
    查询当前用户接口 (Secured)
    """
    # current_user 已经在 deps.py 中完成了鉴权、查库和状态校验
    # 直接返回即可，无需再次查询 Service
    req_id = getattr(request.state, "request_id", None)

    return ResponseModel.success(
        data=UserRead.model_validate(current_user),
        request_id=req_id,
    )


@router.patch(
    "/me",
    response_model=ResponseModel[UserRead],
    summary="更新我的个人资料",
    description="更新当前登录用户的资料。支持修改密码、昵称等。需携带有效 Token。",
)
async def update_user_me(
    request: Request,
    user_in: UserUpdate,
    current_user: CurrentUser,  # ✅ 核心：确保只能修改自己
    service: UserServiceDep,
) -> ResponseModel[UserRead]:
    """
    更新当前用户接口 (Secured)
    """
    # 调用 Service 更新
    # 注意：这里传入 current_user.id，确保操作的是当前登录用户
    updated_user = await service.update(current_user.id, user_in)

    req_id = getattr(request.state, "request_id", None)

    return ResponseModel.success(
        data=UserRead.model_validate(updated_user),
        request_id=req_id,
        message=UserMsg.UPDATE_SUCCESS,
    )


@router.delete(
    "/me",
    response_model=ResponseModel[None],
    status_code=status.HTTP_200_OK,
    summary="注销账户",
    description="永久注销当前登录用户的账户（软删除）。需携带有效 Token。",
)
async def delete_user_me(
    request: Request,
    current_user: CurrentUser,
    service: UserServiceDep,
) -> ResponseModel[None]:
    """
    删除当前用户接口 (Secured)
    """
    await service.delete(current_user.id)

    req_id = getattr(request.state, "request_id", None)

    return ResponseModel.success(
        data=None,
        request_id=req_id,
        message=UserMsg.DELETE_SUCCESS,
    )
