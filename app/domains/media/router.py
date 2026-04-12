"""
File: app/domains/media/router.py
Description: 媒体文件对外挂载路由 (目前强锁定 B 端)

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, Query, Request, UploadFile

from app.api.deps import CurrentAdmin
from app.core.response import ResponseModel
from app.domains.media.dependencies import MediaServiceDep
from app.domains.media.schemas import MediaAssetRead, MediaUploadResult

media_admin = APIRouter()


@media_admin.post(
    "/upload",
    response_model=ResponseModel[MediaUploadResult],
    summary="（后台）核心多媒体文件上传通道",
)
async def upload_material(
    request: Request,
    admin: CurrentAdmin,
    service: MediaServiceDep,
    file: UploadFile = File(...),
) -> ResponseModel[Any]:
    """
    接收上传的原始图像。
    内部同步完成压缩与切片分离，直接吐出包含源图、标清与缩图的完全路径供业务绑定使用。
    """
    result = await service.upload_image(file, admin.id, request)
    await service.db.commit()
    return ResponseModel.success(data=result)


@media_admin.get(
    "",
    response_model=ResponseModel[list[MediaAssetRead]],
    summary="（后台）媒体素材库列表",
)
async def list_materials(
    request: Request,
    admin: CurrentAdmin,
    service: MediaServiceDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> ResponseModel[Any]:
    items = await service.get_admin_materials(skip, limit)
    return ResponseModel.success(data=items)


@media_admin.delete(
    "/{asset_id}",
    response_model=ResponseModel,
    summary="（后台）移除素材并物理抹除",
)
async def delete_material(
    request: Request,
    asset_id: UUID,
    admin: CurrentAdmin,
    service: MediaServiceDep,
) -> ResponseModel[Any]:
    await service.delete_material(asset_id)
    await service.db.commit()
    return ResponseModel.success()
