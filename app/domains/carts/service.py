"""
File: app/domains/carts/service.py
Description: 购物车核心挂载业务与“价格嗅探组合”层

Author: jinmozhe
Created: 2026-04-12
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.db.models.cart import CartItem
from app.db.models.user import User
from app.domains.carts.constants import CartError
from app.domains.carts.repository import CartRepository
from app.domains.carts.schemas import CartItemAddReq, CartItemPatchReq, CartItemRead
from app.domains.products.constants import ProductStatus
from app.domains.products.repository import ProductRepository, ProductSkuRepository
from app.domains.products.schemas import ProductRead, ProductSkuRead
from app.domains.products.service import ProductService


class CartService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CartRepository(db)
        
        # 挂载旁路领域仓储 (读取信息与价格引擎)
        self.product_svc = ProductService(db)
        self.product_repo = ProductRepository(db)
        self.sku_repo = ProductSkuRepository(db)

    def _resolve_identity(self, user: Optional[User], anonymous_id: Optional[str]) -> tuple[Optional[UUID], Optional[str]]:
        """萃取挂车身份主轴（实名压倒一切）"""
        if user:
            return user.id, None
        if anonymous_id:
            return None, anonymous_id
        raise AppException(CartError.MISSING_IDENTITY)

    async def add_item(self, payload: CartItemAddReq, user: Optional[User], anonymous_id: Optional[str]) -> CartItem:
        """纯装弹入库（带 Python 级去重合并防爆）"""
        uid, anon = self._resolve_identity(user, anonymous_id)
        
        # 1. 拦截废弃/无源商品恶意挂车
        product = await self.product_repo.get_by_id(payload.product_id)
        if not product or product.is_deleted or product.status != ProductStatus.ON_SALE:
            raise AppException(CartError.PRODUCT_ERROR)

        if payload.sku_id:
            sku = await self.sku_repo.get_by_id(payload.sku_id)
            if not sku or not sku.is_active or sku.product_id != product.id:
                 raise AppException(CartError.PRODUCT_ERROR)
            if sku.stock < payload.quantity:
                 raise AppException(CartError.STOCK_INSUFFICIENT)
        else:
            if product.stock is not None and product.stock < payload.quantity:
                raise AppException(CartError.STOCK_INSUFFICIENT)

        # 2. 从自身大盘拉寻旧档
        existing = await self.repo.find_exact_item(uid, anon, payload.product_id, payload.sku_id)
        
        if existing:
            # 在库聚变叠加
            existing.quantity += payload.quantity
            return existing
        else:
            # 纯新开单
            new_item = CartItem(
                user_id=uid,
                anonymous_id=anon,
                product_id=payload.product_id,
                sku_id=payload.sku_id,
                quantity=payload.quantity,
                selected=True
            )
            self.db.add(new_item)
            return new_item

    async def patch_item(self, item_id: UUID, payload: CartItemPatchReq, user: Optional[User], anonymous_id: Optional[str]) -> None:
        """改加减号或换打勾状态"""
        uid, anon = self._resolve_identity(user, anonymous_id)
        
        item = await self.repo.get_by_id(item_id, uid, anon)
        if not item:
            raise AppException(CartError.CART_ITEM_NOT_FOUND)

        if payload.quantity is not None:
            item.quantity = payload.quantity
        if payload.selected is not None:
            item.selected = payload.selected

    async def remove_items(self, ids: list[UUID], user: Optional[User], anonymous_id: Optional[str]) -> None:
        """批量倒垃圾"""
        uid, anon = self._resolve_identity(user, anonymous_id)
        await self.repo.batch_delete(ids, uid, anon)

    async def merge_guest_cart(self, user: User, anonymous_id: Optional[str]) -> None:
        """核心登陆聚变过户"""
        if not anonymous_id:
            return
        await self.repo.merge_guest_to_user(anonymous_id, user.id)

    async def get_full_cart_display(self, user: Optional[User], anonymous_id: Optional[str]) -> list[CartItemRead]:
        """
        🚀 雷达阵列展示引擎 (防价格雪崩核心)
        读取出所有底盘记录，再一条一条去查最新的降价状态。
        """
        uid, anon = self._resolve_identity(user, anonymous_id)
        items = await self.repo.get_my_items(uid, anon)

        # 这个号的常客特权
        user_level_id = user.level_id if user else None
        
        # NOTE: 针对多商品应该使用 DataLoader 缓冲优化，由于我们是全聚合模式且推车商品不多，走单次 await。
        result = []
        for v in items:
            p = await self.product_repo.get_by_id(v.product_id)
            sku = await self.sku_repo.get_by_id(v.sku_id) if v.sku_id else None
            
            # --- 雷达判死活 ---
            # 真死亡: 物流都不存在或被硬切了软删除
            if not p or p.is_deleted:
                is_valid = False
            # 假死亡: 停售下架草稿状态
            elif p.status != ProductStatus.ON_SALE:
                is_valid = False
            # 规格死亡: 这规格停牌不用了
            elif v.sku_id and (not sku or not sku.is_active):
                is_valid = False
            else:
                is_valid = True
                
            # --- 前线雷达爆破最新价 ---
            # 在合法前提下使用上一带战功显赫的 `5筛算价斗室` 重验当下最终售价
            realtime_price = p.base_price if p else 0
            member_tag = None
            if is_valid:
                # 注：如果未登录，user_level_id 传 None 则漏斗自动切回原始原价
                # 只有真正获取 UserLevel 的 discount_rate 才需要，这里我们在 UserService 查，但为了解耦，直接给个 1.0 先，或者假设业务目前大多靠 level_prices 硬设。
                # 完善：真实环境下可依赖全局缓存 `await _get_user_discount(user)`，这里传 None。
                realtime_price, member_tag = await self.product_svc.get_display_price(
                    product=p, 
                    sku_id=v.sku_id, 
                    user_level_id=user_level_id, 
                    user_level_discount_rate=None 
                )

            # --- 库存警报器 ---
            is_stock_ok = False
            if is_valid:
                cur_stock = sku.stock if sku else p.stock
                if cur_stock is not None and cur_stock >= v.quantity:
                    is_stock_ok = True

            # 拼装完美呈现柜
            if p:
                assembled = CartItemRead(
                    id=v.id,
                    product_id=v.product_id,
                    sku_id=v.sku_id,
                    quantity=v.quantity,
                    selected=v.selected,
                    is_valid=is_valid,
                    realtime_price=realtime_price,
                    is_stock_ok=is_stock_ok,
                    member_tag=member_tag,
                    product=ProductRead.model_validate(p),
                    sku=ProductSkuRead.model_validate(sku) if sku else None
                )
                result.append(assembled)
                
        return result
