"""
File: app/domains/products/router.py
Description: 商品领域双端路由

C 端：商品浏览（分类树、列表、详情）
B 端：商品管理全生命周期（分类 CRUD、商品 CRUD、SKU/规格/等级价/分佣批量管理）

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request, BackgroundTasks

from app.api.deps import CurrentAdmin, CurrentUser
from app.core.response import ResponseModel
from app.domains.products.constants import ProductStatus, ProductType
from app.domains.products.dependencies import ProductServiceDep
from app.domains.products.schemas import (
    BatchSetCategoryIdsReq,
    BatchSetLevelCommissionsReq,
    BatchSetLevelPricesReq,
    BatchSetSkusReq,
    BatchSetSpecsReq,
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    ProductCreate,
    ProductDetailRead,
    ProductRead,
    ProductStatusUpdate,
    ProductUpdate,
    ProductViewItem,
)

# C 端路由器
product_router = APIRouter()

# B 端路由器
product_admin = APIRouter()


# ==============================================================================
# C 端接口
# ==============================================================================


@product_router.get(
    "/categories",
    response_model=ResponseModel[list],
    summary="获取分类树",
)
async def get_category_tree(
    request: Request,
    service: ProductServiceDep,
) -> ResponseModel[Any]:
    """获取所有启用分类的树形结构"""
    tree = await service.get_category_tree(active_only=True)
    # 序列化树
    def serialize_node(node: dict) -> dict:
        cat = node["category"]
        return {
            "id": str(cat.id),
            "name": cat.name,
            "parent_id": str(cat.parent_id) if cat.parent_id else None,
            "icon_url": cat.icon_url,
            "sort_order": cat.sort_order,
            "children": [serialize_node(c) for c in node["children"]],
        }

    result = [serialize_node(n) for n in tree]
    return ResponseModel.success(data=result)


@product_router.get(
    "",
    response_model=ResponseModel[list[ProductRead]],
    summary="商品列表",
)
async def get_product_list(
    request: Request,
    service: ProductServiceDep,
    category_id: UUID | None = Query(default=None, description="分类筛选"),
    product_type: ProductType | None = Query(default=None, description="商品类型"),
    keyword: str | None = Query(default=None, description="关键词搜索"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> ResponseModel[Any]:
    products = await service.product_repo.get_list(
        category_id=category_id,
        product_type=product_type,
        status=ProductStatus.ON_SALE,
        keyword=keyword,
        skip=skip,
        limit=limit,
    )
    return ResponseModel.success(data=products)


@product_router.get(
    "/{product_id}",
    response_model=ResponseModel[ProductDetailRead],
    summary="商品详情",
)
async def get_product_detail(
    request: Request,
    product_id: UUID,
    service: ProductServiceDep,
) -> ResponseModel[Any]:
    detail = await service.get_product_detail(product_id)
    product = detail["product"]

    # 仅在售商品允许 C 端查看
    if product.status != ProductStatus.ON_SALE:
        from app.domains.products.constants import ProductError
        from app.core.exceptions import AppException
        raise AppException(ProductError.PRODUCT_NOT_FOUND)

    return ResponseModel.success(data={
        **ProductRead.model_validate(product).model_dump(),
        "categories": [CategoryRead.model_validate(c).model_dump() for c in detail["categories"]],
        "specs": detail["specs"],
        "skus": detail["skus"],
    })


@product_router.post(
    "/{product_id}/view",
    response_model=ResponseModel,
    summary="（前端上报）静默记录足迹",
)
async def record_my_view(
    request: Request,
    product_id: UUID,
    user: CurrentUser,
    service: ProductServiceDep,
    background_tasks: BackgroundTasks,
) -> ResponseModel[Any]:
    """
    当页面渲染完毕且用户停留特定时间后，向此处发送上报以留下真实足迹。
    全异步无阻塞处理。
    """
    background_tasks.add_task(service.record_user_view, user.id, product_id)
    return ResponseModel.success()


@product_router.get(
    "/my-views/list",
    response_model=ResponseModel[list[ProductViewItem]],
    summary="我的浏览足迹",
)
async def get_my_views(
    request: Request,
    user: CurrentUser,
    service: ProductServiceDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> ResponseModel[Any]:
    """
    返回当前登录用户的防重历史足迹时间线。
    """
    items = await service.get_my_views(user.id, skip, limit)
    
    # 将字典结构转换为带有验证的对应模型结构
    result = []
    for item in items:
        result.append(
            ProductViewItem(
                viewed_at=item["viewed_at"],
                product=ProductRead.model_validate(item["product"])
            )
        )

    return ResponseModel.success(data=result)



# ==============================================================================
# B 端分类管理
# ==============================================================================


@product_admin.get(
    "/categories",
    response_model=ResponseModel[list],
    summary="（后台）分类列表",
)
async def admin_get_categories(
    request: Request,
    admin: CurrentAdmin,
    service: ProductServiceDep,
) -> ResponseModel[Any]:
    tree = await service.get_category_tree(active_only=False)
    def serialize_node(node: dict) -> dict:
        cat = node["category"]
        return {
            "id": str(cat.id),
            "name": cat.name,
            "parent_id": str(cat.parent_id) if cat.parent_id else None,
            "icon_url": cat.icon_url,
            "sort_order": cat.sort_order,
            "is_active": cat.is_active,
            "level_prices": cat.level_prices,
            "level_commissions": cat.level_commissions,
            "children": [serialize_node(c) for c in node["children"]],
        }
    result = [serialize_node(n) for n in tree]
    return ResponseModel.success(data=result)


@product_admin.post(
    "/categories",
    response_model=ResponseModel[CategoryRead],
    summary="（后台）创建分类",
)
async def admin_create_category(
    request: Request,
    payload: CategoryCreate,
    admin: CurrentAdmin,
    service: ProductServiceDep,
) -> ResponseModel[Any]:
    category = await service.create_category(payload.model_dump())
    await service.db.commit()
    return ResponseModel.success(data=category)


@product_admin.patch(
    "/categories/{category_id}",
    response_model=ResponseModel[CategoryRead],
    summary="（后台）编辑分类",
)
async def admin_update_category(
    request: Request,
    category_id: UUID,
    payload: CategoryUpdate,
    admin: CurrentAdmin,
    service: ProductServiceDep,
) -> ResponseModel[Any]:
    category = await service.update_category(
        category_id, payload.model_dump(exclude_unset=True)
    )
    await service.db.commit()
    return ResponseModel.success(data=category)


@product_admin.delete(
    "/categories/{category_id}",
    response_model=ResponseModel,
    summary="（后台）删除分类",
)
async def admin_delete_category(
    request: Request,
    category_id: UUID,
    admin: CurrentAdmin,
    service: ProductServiceDep,
) -> ResponseModel[Any]:
    await service.delete_category(category_id)
    await service.db.commit()
    return ResponseModel.success()


# ==============================================================================
# B 端商品管理
# ==============================================================================


@product_admin.get(
    "",
    response_model=ResponseModel[list[ProductRead]],
    summary="（后台）商品管理列表",
)
async def admin_get_products(
    request: Request,
    admin: CurrentAdmin,
    service: ProductServiceDep,
    category_id: UUID | None = Query(default=None),
    product_type: ProductType | None = Query(default=None),
    status: ProductStatus | None = Query(default=None),
    keyword: str | None = Query(default=None),
    include_deleted: bool = Query(default=False, description="是否包含已删除"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> ResponseModel[Any]:
    products = await service.product_repo.get_list(
        category_id=category_id,
        product_type=product_type,
        status=status,
        keyword=keyword,
        include_deleted=include_deleted,
        skip=skip,
        limit=limit,
    )
    return ResponseModel.success(data=products)


@product_admin.post(
    "",
    response_model=ResponseModel[ProductRead],
    summary="（后台）创建商品",
)
async def admin_create_product(
    request: Request,
    payload: ProductCreate,
    admin: CurrentAdmin,
    service: ProductServiceDep,
) -> ResponseModel[Any]:
    product = await service.create_product(payload.model_dump())
    await service.db.commit()
    return ResponseModel.success(data=product)


@product_admin.patch(
    "/{product_id}",
    response_model=ResponseModel[ProductRead],
    summary="（后台）更新商品信息",
)
async def admin_update_product(
    request: Request,
    product_id: UUID,
    payload: ProductUpdate,
    admin: CurrentAdmin,
    service: ProductServiceDep,
) -> ResponseModel[Any]:
    product = await service.update_product(
        product_id, payload.model_dump(exclude_unset=True)
    )
    await service.db.commit()
    return ResponseModel.success(data=product)


@product_admin.patch(
    "/{product_id}/status",
    response_model=ResponseModel[ProductRead],
    summary="（后台）上架/下架/草稿",
)
async def admin_update_product_status(
    request: Request,
    product_id: UUID,
    payload: ProductStatusUpdate,
    admin: CurrentAdmin,
    service: ProductServiceDep,
) -> ResponseModel[Any]:
    product = await service.update_product_status(product_id, payload.status)
    await service.db.commit()
    return ResponseModel.success(data=product)


@product_admin.delete(
    "/{product_id}",
    response_model=ResponseModel,
    summary="（后台）软删除商品",
)
async def admin_delete_product(
    request: Request,
    product_id: UUID,
    admin: CurrentAdmin,
    service: ProductServiceDep,
) -> ResponseModel[Any]:
    await service.soft_delete_product(product_id)
    await service.db.commit()
    return ResponseModel.success()


# ==============================================================================
# B 端批量设置
# ==============================================================================


@product_admin.put(
    "/{product_id}/specs",
    response_model=ResponseModel,
    summary="（后台）批量设置规格模板",
)
async def admin_set_specs(
    request: Request,
    product_id: UUID,
    payload: BatchSetSpecsReq,
    admin: CurrentAdmin,
    service: ProductServiceDep,
) -> ResponseModel[Any]:
    await service.replace_specs(
        product_id, [s.model_dump() for s in payload.specs]
    )
    await service.db.commit()
    return ResponseModel.success()


@product_admin.put(
    "/{product_id}/skus",
    response_model=ResponseModel,
    summary="（后台）批量设置 SKU",
)
async def admin_set_skus(
    request: Request,
    product_id: UUID,
    payload: BatchSetSkusReq,
    admin: CurrentAdmin,
    service: ProductServiceDep,
) -> ResponseModel[Any]:
    await service.replace_skus(
        product_id, [s.model_dump() for s in payload.skus]
    )
    await service.db.commit()
    return ResponseModel.success()


@product_admin.put(
    "/{product_id}/level-prices",
    response_model=ResponseModel,
    summary="（后台）批量设置等级价",
)
async def admin_set_level_prices(
    request: Request,
    product_id: UUID,
    payload: BatchSetLevelPricesReq,
    admin: CurrentAdmin,
    service: ProductServiceDep,
) -> ResponseModel[Any]:
    await service.replace_level_prices(
        product_id, [i.model_dump() for i in payload.items]
    )
    await service.db.commit()
    return ResponseModel.success()


@product_admin.put(
    "/{product_id}/level-commissions",
    response_model=ResponseModel,
    summary="（后台）批量设置独立分佣",
)
async def admin_set_level_commissions(
    request: Request,
    product_id: UUID,
    payload: BatchSetLevelCommissionsReq,
    admin: CurrentAdmin,
    service: ProductServiceDep,
) -> ResponseModel[Any]:
    await service.replace_level_commissions(
        product_id, [i.model_dump() for i in payload.items]
    )
    await service.db.commit()
    return ResponseModel.success()


@product_admin.put(
    "/{product_id}/categories",
    response_model=ResponseModel,
    summary="（后台）批量设置所属分类",
)
async def admin_set_categories(
    request: Request,
    product_id: UUID,
    payload: BatchSetCategoryIdsReq,
    admin: CurrentAdmin,
    service: ProductServiceDep,
) -> ResponseModel[Any]:
    await service.replace_categories(product_id, payload.category_ids)
    await service.db.commit()
    return ResponseModel.success()
