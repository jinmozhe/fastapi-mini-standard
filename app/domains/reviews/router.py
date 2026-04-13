"""
File: app/domains/reviews/router.py
Description: 评价 C 端路由

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentUser
from app.core.response import ResponseModel
from app.domains.reviews.dependencies import ReviewServiceDep
from app.domains.reviews.schemas import (
    ReviewCreateReq,
    ReviewPageResult,
    ReviewRead,
)

review_router = APIRouter()


@review_router.post(
    "/",
    response_model=ResponseModel[ReviewRead],
    summary="提交评价",
)
async def create_review(
    request: Request,
    body: ReviewCreateReq,
    user: CurrentUser,
    service: ReviewServiceDep,
) -> ResponseModel[Any]:
    """对已完成订单的商品提交评价"""
    review = await service.create_review(user.id, body)
    await service.db.commit()
    return ResponseModel.success(data=ReviewRead.model_validate(review))


@review_router.get(
    "/product/{product_id}",
    response_model=ResponseModel[ReviewPageResult],
    summary="商品评价列表",
)
async def list_product_reviews(
    request: Request,
    product_id: UUID,
    service: ReviewServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> ResponseModel[Any]:
    """某商品的所有评价"""
    rows, total = await service.repo.list_by_product(product_id, page, page_size)
    items = [ReviewRead.model_validate(r) for r in rows]
    return ResponseModel.success(data=ReviewPageResult(
        items=items, total=total, page=page, page_size=page_size,
    ))


@review_router.get(
    "/mine",
    response_model=ResponseModel[ReviewPageResult],
    summary="我的评价",
)
async def list_my_reviews(
    request: Request,
    user: CurrentUser,
    service: ReviewServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> ResponseModel[Any]:
    """我发表的评价"""
    rows, total = await service.repo.list_by_user(user.id, page, page_size)
    items = [ReviewRead.model_validate(r) for r in rows]
    return ResponseModel.success(data=ReviewPageResult(
        items=items, total=total, page=page, page_size=page_size,
    ))
