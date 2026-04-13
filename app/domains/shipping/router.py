"""
File: app/domains/shipping/router.py
Description: 运费模板 B 端管理接口

所有接口仅限 B 端管理员（aud=backend）访问。
运费计算引擎不暴露独立接口，由结算域内部调用 ShippingService.calculate_freight()。

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentAdmin
from app.core.response import ResponseModel
from app.domains.shipping.dependencies import ShippingServiceDep
from app.domains.shipping.schemas import (
    ShippingTemplateCreate,
    ShippingTemplateListItem,
    ShippingTemplatePageResult,
    ShippingTemplateRead,
    ShippingTemplateUpdate,
    ShippingRegionRead,
)

shipping_admin = APIRouter()


@shipping_admin.post(
    "",
    response_model=ResponseModel[ShippingTemplateRead],
    summary="创建运费模板",
)
async def create_template(
    request: Request,
    admin: CurrentAdmin,
    payload: ShippingTemplateCreate,
    service: ShippingServiceDep,
) -> ResponseModel[Any]:
    """
    创建运费模板，需同时提交地区运费规则。
    规则中必须包含一条 province_codes 为空数组的「其余地区」兜底规则。
    """
    template = await service.create_template(payload)
    await service.db.commit()

    # 重新加载完整数据
    detail = await service.get_template_detail(template.id)
    result = ShippingTemplateRead(
        id=detail["template"].id,
        name=detail["template"].name,
        pricing_method=detail["template"].pricing_method,
        free_shipping_threshold=detail["template"].free_shipping_threshold,
        free_shipping_exclude_regions=detail["template"].free_shipping_exclude_regions,
        is_active=detail["template"].is_active,
        regions=[ShippingRegionRead.model_validate(r) for r in detail["regions"]],
        created_at=detail["template"].created_at,
        updated_at=detail["template"].updated_at,
    )
    return ResponseModel.success(data=result)


@shipping_admin.get(
    "",
    response_model=ResponseModel[ShippingTemplatePageResult],
    summary="运费模板列表",
)
async def list_templates(
    request: Request,
    admin: CurrentAdmin,
    service: ShippingServiceDep,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 20,
) -> ResponseModel[Any]:
    """分页查询运费模板列表。"""
    rows, total = await service.repo.list_all(page=page, page_size=page_size)

    items = []
    for t in rows:
        region_count = await service.repo.count_region(t.id)
        items.append(ShippingTemplateListItem(
            id=t.id,
            name=t.name,
            pricing_method=t.pricing_method,
            free_shipping_threshold=t.free_shipping_threshold,
            is_active=t.is_active,
            region_count=region_count,
            created_at=t.created_at,
        ))

    result = ShippingTemplatePageResult(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
    return ResponseModel.success(data=result)


@shipping_admin.get(
    "/{template_id}",
    response_model=ResponseModel[ShippingTemplateRead],
    summary="运费模板详情",
)
async def get_template_detail(
    request: Request,
    admin: CurrentAdmin,
    template_id: UUID,
    service: ShippingServiceDep,
) -> ResponseModel[Any]:
    """获取运费模板详情（含全部地区规则）。"""
    detail = await service.get_template_detail(template_id)
    result = ShippingTemplateRead(
        id=detail["template"].id,
        name=detail["template"].name,
        pricing_method=detail["template"].pricing_method,
        free_shipping_threshold=detail["template"].free_shipping_threshold,
        free_shipping_exclude_regions=detail["template"].free_shipping_exclude_regions,
        is_active=detail["template"].is_active,
        regions=[ShippingRegionRead.model_validate(r) for r in detail["regions"]],
        created_at=detail["template"].created_at,
        updated_at=detail["template"].updated_at,
    )
    return ResponseModel.success(data=result)


@shipping_admin.put(
    "/{template_id}",
    response_model=ResponseModel[ShippingTemplateRead],
    summary="修改运费模板",
)
async def update_template(
    request: Request,
    admin: CurrentAdmin,
    template_id: UUID,
    payload: ShippingTemplateUpdate,
    service: ShippingServiceDep,
) -> ResponseModel[Any]:
    """全量修改运费模板（地区规则整体替换）。"""
    await service.update_template(template_id, payload)
    await service.db.commit()

    detail = await service.get_template_detail(template_id)
    result = ShippingTemplateRead(
        id=detail["template"].id,
        name=detail["template"].name,
        pricing_method=detail["template"].pricing_method,
        free_shipping_threshold=detail["template"].free_shipping_threshold,
        free_shipping_exclude_regions=detail["template"].free_shipping_exclude_regions,
        is_active=detail["template"].is_active,
        regions=[ShippingRegionRead.model_validate(r) for r in detail["regions"]],
        created_at=detail["template"].created_at,
        updated_at=detail["template"].updated_at,
    )
    return ResponseModel.success(data=result)


@shipping_admin.delete(
    "/{template_id}",
    response_model=ResponseModel,
    summary="删除运费模板",
)
async def delete_template(
    request: Request,
    admin: CurrentAdmin,
    template_id: UUID,
    service: ShippingServiceDep,
) -> ResponseModel[Any]:
    """
    软删除运费模板。
    若仍有商品引用该模板，则拒绝删除。
    """
    await service.delete_template(template_id)
    await service.db.commit()
    return ResponseModel.success()
