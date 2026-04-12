"""
File: app/domains/products/dependencies.py
Description: 商品领域依赖注入容器

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.domains.products.service import ProductService


async def get_product_service(db: AsyncSession = Depends(get_db)) -> ProductService:
    """提供 ProductService 单例"""
    return ProductService(db)


ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
