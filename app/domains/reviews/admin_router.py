"""
File: app/domains/reviews/admin_router.py
Description: 评价 B 端管理路由

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.core.response import ResponseModel
from app.domains.reviews.dependencies import ReviewServiceDep
from app.domains.reviews.schemas import (
    ReviewPageResult,
    ReviewRead,
    ReviewReplyReq,
    ReviewVisibilityReq,
)

review_admin = APIRouter()


@review_admin.get(
    "/",
    response_model=ResponseModel[ReviewPageResult],
    summary="B端评价列表",
)
async def admin_list_reviews(
    request: Request,
    service: ReviewServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> ResponseModel[Any]:
    """全量评价列表"""
    rows, total = await service.repo.list_all(page, page_size)
    items = [ReviewRead.model_validate(r) for r in rows]
    return ResponseModel.success(data=ReviewPageResult(
        items=items, total=total, page=page, page_size=page_size,
    ))


@review_admin.patch(
    "/{review_id}/reply",
    summary="商家回复",
)
async def admin_reply_review(
    request: Request,
    review_id: UUID,
    body: ReviewReplyReq,
    service: ReviewServiceDep,
) -> ResponseModel[Any]:
    """回复用户评价"""
    await service.reply_review(review_id, body.reply_content)
    await service.db.commit()
    return ResponseModel.success(message="回复成功")


@review_admin.patch(
    "/{review_id}/visibility",
    summary="设置评价可见性",
)
async def admin_set_visibility(
    request: Request,
    review_id: UUID,
    body: ReviewVisibilityReq,
    service: ReviewServiceDep,
) -> ResponseModel[Any]:
    """显示或隐藏评价"""
    await service.set_visibility(review_id, body.is_visible)
    await service.db.commit()
    return ResponseModel.success(message="设置成功")
