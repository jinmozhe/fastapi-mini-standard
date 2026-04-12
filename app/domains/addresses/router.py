"""
File: app/domains/addresses/router.py
Description: 收货地址 C端接口（仅限已登录用户）

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request

from app.api.deps import CurrentUser
from app.core.response import ResponseModel
from app.domains.addresses.dependencies import AddressServiceDep
from app.domains.addresses.schemas import AddressCreate, AddressRead, AddressUpdate

address_router = APIRouter()


@address_router.post(
    "",
    response_model=ResponseModel[AddressRead],
    summary="新建收货地址",
)
async def create_address(
    request: Request,
    payload: AddressCreate,
    user: CurrentUser,
    service: AddressServiceDep,
) -> ResponseModel[Any]:
    """
    新建收货地址。
    - 若是用户第一条地址，自动设为默认。
    - 若提交时指定 is_default=true，同样触发互斥切换引擎。
    - 单用户上限 20 条。
    """
    address = await service.create_address(user.id, payload)
    await service.db.commit()
    return ResponseModel.success(data=address)


@address_router.get(
    "",
    response_model=ResponseModel[list[AddressRead]],
    summary="获取我的地址列表",
)
async def get_my_addresses(
    request: Request,
    user: CurrentUser,
    service: AddressServiceDep,
) -> ResponseModel[Any]:
    """返回当前用户所有收货地址，默认地址排第一。"""
    addresses = await service.get_list(user.id)
    return ResponseModel.success(data=addresses)


@address_router.get(
    "/default",
    response_model=ResponseModel[AddressRead | None],
    summary="获取默认地址（结算页专用）",
)
async def get_default_address(
    request: Request,
    user: CurrentUser,
    service: AddressServiceDep,
) -> ResponseModel[Any]:
    """快速获取当前默认地址，供结算页预填充。若无地址则返回 null。"""
    address = await service.get_default(user.id)
    return ResponseModel.success(data=address)


@address_router.put(
    "/{address_id}",
    response_model=ResponseModel[AddressRead],
    summary="修改收货地址",
)
async def update_address(
    request: Request,
    address_id: UUID,
    payload: AddressUpdate,
    user: CurrentUser,
    service: AddressServiceDep,
) -> ResponseModel[Any]:
    """全量修改收货地址。若修改时将 is_default 设为 true 则触发互斥切换引擎。"""
    address = await service.update_address(user.id, address_id, payload)
    await service.db.commit()
    return ResponseModel.success(data=address)


@address_router.patch(
    "/{address_id}/set-default",
    response_model=ResponseModel,
    summary="切换默认地址",
)
async def set_default_address(
    request: Request,
    address_id: UUID,
    user: CurrentUser,
    service: AddressServiceDep,
) -> ResponseModel[Any]:
    """将指定地址设为默认，同时清除原默认标记。"""
    await service.set_default(user.id, address_id)
    await service.db.commit()
    return ResponseModel.success()


@address_router.delete(
    "/{address_id}",
    response_model=ResponseModel,
    summary="删除收货地址",
)
async def delete_address(
    request: Request,
    address_id: UUID,
    user: CurrentUser,
    service: AddressServiceDep,
) -> ResponseModel[Any]:
    """
    物理删除收货地址。
    若删除的是默认地址，系统自动将最早创建的地址晋升为新默认。
    """
    await service.delete_address(user.id, address_id)
    await service.db.commit()
    return ResponseModel.success()


# ==============================================================================
# B 端管理员路由（仅限 aud=backend Token）
# ==============================================================================

from typing import Annotated  # noqa: E402（避免与上方 import 拆分）
from uuid import UUID as _UUID

from fastapi import Query  # noqa: E402

from app.api.deps import CurrentAdmin  # noqa: E402
from app.domains.addresses.schemas import AddressPageResult  # noqa: E402

address_admin = APIRouter()


@address_admin.get(
    "",
    response_model=ResponseModel[AddressPageResult],
    summary="[B端] 查询用户收货地址列表",
)
async def admin_list_addresses(
    request: Request,
    admin: CurrentAdmin,
    service: AddressServiceDep,
    user_id: Annotated[_UUID | None, Query(description="按用户 ID 过滤（不传则查全部）")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 20,
) -> ResponseModel[Any]:
    """
    B 端分页查询所有用户的收货地址。
    支持按 user_id 过滤，用于运营/客服调查特定用户的地址信息。
    """
    rows, total = await service.repo.admin_list_all(
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    result = AddressPageResult(
        items=rows,
        total=total,
        page=page,
        page_size=page_size,
    )
    return ResponseModel.success(data=result)
