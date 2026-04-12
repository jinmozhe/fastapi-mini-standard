"""
File: app/domains/carts/repository.py
Description: 购物车持久库交互

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.cart import CartItem


class CartRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _build_identity_filter(self, stmt, user_id: Optional[UUID], anonymous_id: Optional[str]):
        """辅助器：确保查询牢牢锁定自己的购物车"""
        if user_id:
            return stmt.where(CartItem.user_id == user_id)
        elif anonymous_id:
            return stmt.where(CartItem.anonymous_id == anonymous_id, CartItem.user_id.is_(None))
        else:
            # 异常态：必须卡掉
            return stmt.where(CartItem.id == None)

    async def get_my_items(
        self, user_id: Optional[UUID], anonymous_id: Optional[str]
    ) -> Sequence[CartItem]:
        """按时间倒序拿回购物车全盘资料"""
        stmt = select(CartItem)
        stmt = self._build_identity_filter(stmt, user_id, anonymous_id)
        stmt = stmt.order_by(CartItem.created_at.desc())
        
        result = await self.db.scalars(stmt)
        return result.all()

    async def find_exact_item(
        self, user_id: Optional[UUID], anonymous_id: Optional[str], product_id: UUID, sku_id: Optional[UUID]
    ) -> Optional[CartItem]:
        """用于聚拢判定：看看这个商品之前加没加过"""
        stmt = select(CartItem).where(
            CartItem.product_id == product_id,
            CartItem.sku_id == sku_id
        )
        stmt = self._build_identity_filter(stmt, user_id, anonymous_id)
        return await self.db.scalar(stmt)

    async def get_by_id(
        self, item_id: UUID, user_id: Optional[UUID], anonymous_id: Optional[str]
    ) -> Optional[CartItem]:
        """安全查询一条"""
        stmt = select(CartItem).where(CartItem.id == item_id)
        stmt = self._build_identity_filter(stmt, user_id, anonymous_id)
        return await self.db.scalar(stmt)

    async def batch_delete(
        self, ids: list[UUID], user_id: Optional[UUID], anonymous_id: Optional[str]
    ) -> None:
        """安全清空指定的 IDs"""
        stmt = delete(CartItem).where(CartItem.id.in_(ids))
        stmt = self._build_identity_filter(stmt, user_id, anonymous_id)
        await self.db.execute(stmt)

    async def merge_guest_to_user(self, anonymous_id: str, user_id: UUID) -> None:
        """
        🚀 终极聚变引擎 (Guest Cart -> Member Cart)
        
        这是通过纯 Python 逻辑控制，因为需要实现累加与消除。
        """
        # 1. 取出这台设备所有的匿名历史
        anon_stmt = select(CartItem).where(CartItem.anonymous_id == anonymous_id, CartItem.user_id.is_(None))
        anon_items = (await self.db.scalars(anon_stmt)).all()
        
        if not anon_items:
            return # 这个号毫无挂车痕迹，直接完事
            
        # 2. 取出这老手现有的实名车历史
        user_stmt = select(CartItem).where(CartItem.user_id == user_id)
        user_items = (await self.db.scalars(user_stmt)).all()
        
        # 将老手的家当按 (product, sku) 做个字典目录，加速聚变
        # map key: f"{product_id}_{sku_id}"
        user_map: dict[str, CartItem] = {}
        for ui in user_items:
            k = f"{ui.product_id}_{ui.sku_id or 'none'}"
            user_map[k] = ui

        # 3. 逐个洗盘过户
        for ai in anon_items:
            k = f"{ai.product_id}_{ai.sku_id or 'none'}"
            if k in user_map:
                # 场景 A: 发现实装已经有这个规格了 -> 合并数量！然后把这个老旧的匿名废壳给掐掉
                user_item = user_map[k]
                user_item.quantity += ai.quantity
                await self.db.delete(ai)
            else:
                # 场景 B: 发现是台新货 -> 直接改名过户
                ai.user_id = user_id
                ai.anonymous_id = None
