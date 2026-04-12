"""
File: app/domains/carts/router.py
Description: C端买家与游客购物车接口集

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request

from app.api.deps import CurrentUser, OptionalCurrentUser
from app.core.response import ResponseModel
from app.domains.carts.dependencies import CartServiceDep, DeviceIdHeader
from app.domains.carts.schemas import (
    CartItemAddReq,
    CartItemDeleteReq,
    CartItemPatchReq,
    CartItemRead,
)

cart_router = APIRouter()


@cart_router.post(
    "",
    response_model=ResponseModel,
    summary="[双轨] 加入购物车或增加数量",
)
async def add_to_cart(
    request: Request,
    payload: CartItemAddReq,
    service: CartServiceDep,
    user: OptionalCurrentUser,
    device_id: DeviceIdHeader = None,
) -> ResponseModel[Any]:
    """
    智能将商品或 SKU 装入车兜。
    自动通过指纹/登录身份合并同款数量。
    如果遇到缺货抛出安全保护。
    """
    item = await service.add_item(payload, user, device_id)
    await service.db.commit()
    return ResponseModel.success()


@cart_router.get(
    "/my",
    response_model=ResponseModel[list[CartItemRead]],
    summary="[双轨] 展开我的购物车",
)
async def get_my_cart(
    request: Request,
    service: CartServiceDep,
    user: OptionalCurrentUser,
    device_id: DeviceIdHeader = None,
) -> ResponseModel[Any]:
    """
    取出购物车名下的所有货架资料。
    系统底层会自动套用实时 5 层降价雷达运算最终 display_price。
    并且智能侦测 `is_valid` 判别下架异常。
    """
    results = await service.get_full_cart_display(user, device_id)
    return ResponseModel.success(data=results)


@cart_router.patch(
    "/{item_id}",
    response_model=ResponseModel,
    summary="[双轨] 调整挂车商品状态 (件数或勾勾)",
)
async def patch_cart_item(
    request: Request,
    item_id: UUID,
    payload: CartItemPatchReq,
    service: CartServiceDep,
    user: OptionalCurrentUser,
    device_id: DeviceIdHeader = None,
) -> ResponseModel[Any]:
    """修改指定的打钩或件数"""
    await service.patch_item(item_id, payload, user, device_id)
    await service.db.commit()
    return ResponseModel.success()


@cart_router.delete(
    "",
    response_model=ResponseModel,
    summary="[双轨] 批量移出购物车",
)
async def delete_cart_items(
    request: Request,
    payload: CartItemDeleteReq,
    service: CartServiceDep,
    user: OptionalCurrentUser,
    device_id: DeviceIdHeader = None,
) -> ResponseModel[Any]:
    """传 IDs 清除战团"""
    await service.remove_items(payload.ids, user, device_id)
    await service.db.commit()
    return ResponseModel.success()


@cart_router.post(
    "/merge",
    response_model=ResponseModel,
    summary="[强开] 游客车底盘并网实名库",
)
async def merge_guest_cart(
    request: Request,
    service: CartServiceDep,
    user: CurrentUser,       # 注意：此处强制要求必须持有真实 Token 认证进入
    device_id: DeviceIdHeader = None,
) -> ResponseModel[Any]:
    """
    当小程序获取到了正式用户信息后，拿着老指纹调用本接口触发并网融合。
    """
    await service.merge_guest_cart(user, device_id)
    await service.db.commit()
    return ResponseModel.success()
