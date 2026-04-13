"""
File: app/domains/orders/service.py
Description: 订单核心编排引擎

串联所有上游域：购物车 → 商品价格 → 运费 → 地址快照 → 库存 → 支付 → 佣金

核心方法：
- checkout_preview()  → 结算预览（纯计算）
- create_order()      → 提交订单（锁库存+快照+建单）
- pay_order()         → 去支付（余额/微信）
- cancel_order()      → 用户取消（仅待付款）
- confirm_order()     → 确认收货
- ship_order()        → B 端发货
- force_cancel()      → 管理员强制取消（退款+扣回佣金）

Author: jinmozhe
Created: 2026-04-13
"""

import uuid as uuid_mod
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import logger
from app.db.models.order import Order, OrderItem
from app.domains.orders.commission_service import CommissionService
from app.domains.orders.constants import OrderError, OrderStatus
from app.domains.orders.repository import OrderRepository
from app.domains.orders.schemas import (
    CheckoutItemPreview,
    CheckoutPreviewReq,
    CheckoutPreviewResult,
    OrderCreateReq,
    OrderCreateResult,
    OrderPayReq,
)
from app.domains.products.constants import ProductStatus


class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = OrderRepository(db)
        self.commission_service = CommissionService(db)

    # --------------------------------------------------------------------------
    # 订单编号生成
    # --------------------------------------------------------------------------
    @staticmethod
    def _generate_order_no() -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        rand = str(uuid_mod.uuid4().int)[:6]
        return f"ORD{ts}{rand}"

    # --------------------------------------------------------------------------
    # 1. 结算预览（纯计算，不建单）
    # --------------------------------------------------------------------------
    async def checkout_preview(
        self,
        user_id: UUID,
        data: CheckoutPreviewReq,
    ) -> CheckoutPreviewResult:
        """结算预览：计算实时价格 + 运费"""
        from app.domains.addresses.service import AddressService
        from app.domains.carts.repository import CartRepository
        from app.domains.products.repository import ProductRepository, ProductSkuRepository
        from app.domains.products.service import ProductService
        from app.domains.shipping.service import ShippingService
        from app.db.models.user import User

        cart_repo = CartRepository(self.db)
        product_repo = ProductRepository(self.db)
        sku_repo = ProductSkuRepository(self.db)
        product_svc = ProductService(self.db)
        address_svc = AddressService(self.db)
        shipping_svc = ShippingService(self.db)

        # 1. 获取地址快照
        address_snapshot = await address_svc.get_snapshot(user_id, data.address_id)

        # 2. 获取用户等级
        user = await self.db.get(User, user_id)
        user_level_id = user.level_id if user else None

        # 3. 遍历购物车条目，计算每项
        items: list[CheckoutItemPreview] = []
        items_amount = Decimal("0.00")
        # 按运费模板分组：{template_id: {total_weight, total_piece, subtotal}}
        freight_groups: dict[UUID | None, dict] = {}

        for cart_item_id in data.cart_item_ids:
            cart_item = await cart_repo.get_by_id_for_user(cart_item_id, user_id)
            if not cart_item:
                raise AppException(OrderError.CART_EMPTY)

            product = await product_repo.get_by_id(cart_item.product_id)
            if not product or product.is_deleted or product.status != ProductStatus.ON_SALE:
                raise AppException(OrderError.PRODUCT_UNAVAILABLE)

            sku = None
            weight = Decimal("0.00")
            if cart_item.sku_id:
                sku = await sku_repo.get_by_id(cart_item.sku_id)
                if not sku or not sku.is_active:
                    raise AppException(OrderError.PRODUCT_UNAVAILABLE)
                if sku.stock < cart_item.quantity:
                    raise AppException(OrderError.STOCK_INSUFFICIENT)
                weight = sku.weight
            else:
                if product.stock is not None and product.stock < cart_item.quantity:
                    raise AppException(OrderError.STOCK_INSUFFICIENT)

            # 5级价格引擎
            unit_price, _ = await product_svc.get_display_price(
                product=product,
                sku_id=cart_item.sku_id,
                user_level_id=user_level_id,
            )
            subtotal = unit_price * cart_item.quantity

            items.append(CheckoutItemPreview(
                product_id=product.id,
                sku_id=cart_item.sku_id,
                product_name=product.name,
                product_image=product.main_image,
                sku_spec=sku.spec_values if sku else None,
                unit_price=unit_price,
                quantity=cart_item.quantity,
                subtotal=subtotal,
                weight=weight,
            ))
            items_amount += subtotal

            # 运费分组
            tmpl_id = product.shipping_template_id
            if tmpl_id not in freight_groups:
                freight_groups[tmpl_id] = {"total_weight": Decimal("0"), "total_piece": 0, "subtotal": Decimal("0")}
            freight_groups[tmpl_id]["total_weight"] += weight * cart_item.quantity
            freight_groups[tmpl_id]["total_piece"] += cart_item.quantity
            freight_groups[tmpl_id]["subtotal"] += subtotal

        if not items:
            raise AppException(OrderError.CART_EMPTY)

        # 4. 计算运费
        freight_amount = Decimal("0.00")
        province_code = address_snapshot.province_code or ""

        for tmpl_id, group in freight_groups.items():
            if tmpl_id is None:
                continue  # 无模板 = 包邮
            result = await shipping_svc.calculate_freight(
                template_id=tmpl_id,
                province_code=province_code,
                total_weight_gram=group["total_weight"],
                total_piece=group["total_piece"],
                subtotal=group["subtotal"],
            )
            freight_amount += result.freight

        total_amount = items_amount + freight_amount

        return CheckoutPreviewResult(
            items=items,
            address=address_snapshot.model_dump(),
            items_amount=items_amount,
            freight_amount=freight_amount,
            total_amount=total_amount,
        )

    # --------------------------------------------------------------------------
    # 2. 提交订单（锁库存+快照+建单，不支付）
    # --------------------------------------------------------------------------
    async def create_order(
        self,
        user_id: UUID,
        data: OrderCreateReq,
    ) -> OrderCreateResult:
        """提交订单"""
        from app.domains.addresses.service import AddressService
        from app.domains.carts.repository import CartRepository
        from app.domains.carts.service import CartService
        from app.domains.products.repository import ProductRepository, ProductSkuRepository
        from app.domains.products.service import ProductService
        from app.domains.shipping.service import ShippingService
        from app.db.models.user import User

        cart_repo = CartRepository(self.db)
        product_repo = ProductRepository(self.db)
        sku_repo = ProductSkuRepository(self.db)
        product_svc = ProductService(self.db)
        address_svc = AddressService(self.db)
        shipping_svc = ShippingService(self.db)

        # 1. 地址快照
        address_snapshot = await address_svc.get_snapshot(user_id, data.address_id)

        # 2. 用户等级
        user = await self.db.get(User, user_id)
        user_level_id = user.level_id if user else None

        # 3. 遍历购物车 → 校验+计算+快照+扣库存
        order_items: list[OrderItem] = []
        items_amount = Decimal("0.00")
        freight_groups: dict[UUID | None, dict] = {}
        cart_item_ids_to_remove: list[UUID] = []

        order_no = self._generate_order_no()

        for cart_item_id in data.cart_item_ids:
            cart_item = await cart_repo.get_by_id_for_user(cart_item_id, user_id)
            if not cart_item:
                raise AppException(OrderError.CART_EMPTY)

            product = await product_repo.get_by_id(cart_item.product_id)
            if not product or product.is_deleted or product.status != ProductStatus.ON_SALE:
                raise AppException(OrderError.PRODUCT_UNAVAILABLE)

            sku = None
            weight = Decimal("0.00")
            if cart_item.sku_id:
                sku = await sku_repo.get_by_id(cart_item.sku_id)
                if not sku or not sku.is_active:
                    raise AppException(OrderError.PRODUCT_UNAVAILABLE)
                # 扣库存（乐观锁）
                ok = await sku_repo.deduct_stock(sku.id, cart_item.quantity)
                if not ok:
                    raise AppException(OrderError.STOCK_INSUFFICIENT)
                weight = sku.weight
            else:
                if product.stock is not None:
                    ok = await product_repo.deduct_stock(product.id, cart_item.quantity)
                    if not ok:
                        raise AppException(OrderError.STOCK_INSUFFICIENT)

            # 价格
            unit_price, _ = await product_svc.get_display_price(
                product=product,
                sku_id=cart_item.sku_id,
                user_level_id=user_level_id,
            )
            subtotal = unit_price * cart_item.quantity
            items_amount += subtotal

            # 商品快照
            product_snapshot = {
                "name": product.name,
                "main_image": product.main_image,
                "product_type": product.product_type,
            }
            sku_snapshot = None
            if sku:
                sku_snapshot = {
                    "sku_code": sku.sku_code,
                    "spec_values": sku.spec_values,
                    "image_url": sku.image_url,
                    "weight": float(sku.weight),
                }

            order_items.append(OrderItem(
                product_id=product.id,
                sku_id=cart_item.sku_id,
                product_snapshot=product_snapshot,
                sku_snapshot=sku_snapshot,
                unit_price=unit_price,
                quantity=cart_item.quantity,
                subtotal=subtotal,
            ))

            # 运费分组
            tmpl_id = product.shipping_template_id
            if tmpl_id not in freight_groups:
                freight_groups[tmpl_id] = {"total_weight": Decimal("0"), "total_piece": 0, "subtotal": Decimal("0")}
            freight_groups[tmpl_id]["total_weight"] += weight * cart_item.quantity
            freight_groups[tmpl_id]["total_piece"] += cart_item.quantity
            freight_groups[tmpl_id]["subtotal"] += subtotal

            cart_item_ids_to_remove.append(cart_item_id)

        if not order_items:
            raise AppException(OrderError.CART_EMPTY)

        # 4. 计算运费
        freight_amount = Decimal("0.00")
        province_code = address_snapshot.province_code or ""
        for tmpl_id, group in freight_groups.items():
            if tmpl_id is None:
                continue
            result = await shipping_svc.calculate_freight(
                template_id=tmpl_id,
                province_code=province_code,
                total_weight_gram=group["total_weight"],
                total_piece=group["total_piece"],
                subtotal=group["subtotal"],
            )
            freight_amount += result.freight

        total_amount = items_amount + freight_amount

        # 5. 创建订单
        order = Order(
            order_no=order_no,
            user_id=user_id,
            status=OrderStatus.PENDING_PAYMENT,
            address_snapshot=address_snapshot.model_dump(),
            items_amount=items_amount,
            freight_amount=freight_amount,
            total_amount=total_amount,
            remark=data.remark,
        )
        self.db.add(order)
        await self.db.flush()

        # 6. 创建订单明细
        for item in order_items:
            item.order_id = order.id
            self.db.add(item)

        # 7. 清理购物车
        cart_svc = CartService(self.db)
        await cart_svc.remove_items(cart_item_ids_to_remove, user, None)

        logger.info(
            "order_created",
            order_no=order_no,
            user_id=str(user_id),
            total_amount=str(total_amount),
            item_count=len(order_items),
        )

        return OrderCreateResult(
            order_id=order.id,
            order_no=order.order_no,
            total_amount=order.total_amount,
            status=order.status,
        )

    # --------------------------------------------------------------------------
    # 3. 去支付
    # --------------------------------------------------------------------------
    async def pay_order(
        self,
        user_id: UUID,
        order_id: UUID,
        data: OrderPayReq,
        openid: str | None = None,
    ) -> dict:
        """
        对待付款订单发起支付。
        支付成功后：订单 → pending_shipment + 触发佣金结算
        """
        from app.domains.payments.service import PaymentService
        from app.domains.payments.schemas import PaymentCreateInternal

        order = await self.repo.get_by_id(order_id)
        if not order or order.user_id != user_id:
            raise AppException(OrderError.NOT_FOUND)

        if order.status != OrderStatus.PENDING_PAYMENT:
            raise AppException(OrderError.ALREADY_PAID)

        payment_svc = PaymentService(self.db)
        payment_result = await payment_svc.initiate_payment(
            data=PaymentCreateInternal(
                order_id=order.id,
                user_id=user_id,
                amount=order.total_amount,
                payment_method=data.payment_method,
            ),
            openid=openid,
        )

        # 如果余额支付（即时完成），直接更新订单状态 + 分佣
        if payment_result.status == "paid":
            await self._on_payment_success(order, data.payment_method)

        return {
            "order_id": order.id,
            "order_no": order.order_no,
            "status": order.status,
            "payment_result": payment_result,
        }

    async def _on_payment_success(self, order: Order, payment_method: str) -> None:
        """支付成功后的联动操作"""
        now_iso = datetime.now(timezone.utc).isoformat()
        order.status = OrderStatus.PENDING_SHIPMENT
        order.payment_method = payment_method
        order.paid_at = now_iso

        # 触发佣金结算（根据配置决定冻结/直接入账）
        if settings.COMMISSION_SETTLE_ON == "payment":
            commission_total = await self.commission_service.settle_commissions(order)
            order.commission_total = commission_total

        logger.info(
            "order_paid",
            order_no=order.order_no,
            payment_method=payment_method,
            commission_total=str(order.commission_total),
        )

    async def on_wechat_payment_success(self, order_id: UUID, payment_method: str = "wechat") -> None:
        """微信支付回调成功后调用（从 PaymentService 回调中触发）"""
        order = await self.repo.get_by_id(order_id)
        if order and order.status == OrderStatus.PENDING_PAYMENT:
            await self._on_payment_success(order, payment_method)

    # --------------------------------------------------------------------------
    # 4. 用户取消订单（仅待付款）
    # --------------------------------------------------------------------------
    async def cancel_order(self, user_id: UUID, order_id: UUID) -> None:
        """用户自助取消（仅 pending_payment 状态）"""
        from app.domains.products.repository import ProductRepository, ProductSkuRepository
        from app.domains.payments.service import PaymentService

        order = await self.repo.get_by_id(order_id)
        if not order or order.user_id != user_id:
            raise AppException(OrderError.NOT_FOUND)

        if order.status != OrderStatus.PENDING_PAYMENT:
            raise AppException(OrderError.CANNOT_CANCEL)

        # 恢复库存
        await self._restore_stock(order)

        # 关闭支付
        payment_svc = PaymentService(self.db)
        await payment_svc.close_payment(order.id)

        now_iso = datetime.now(timezone.utc).isoformat()
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = now_iso
        order.cancel_reason = "用户自助取消"
        order.cancelled_by = user_id

        logger.info("order_cancelled_by_user", order_no=order.order_no)

    # --------------------------------------------------------------------------
    # 5. 确认收货
    # --------------------------------------------------------------------------
    async def confirm_order(self, user_id: UUID, order_id: UUID) -> None:
        """买家确认收货"""
        order = await self.repo.get_by_id(order_id)
        if not order or order.user_id != user_id:
            raise AppException(OrderError.NOT_FOUND)

        if order.status != OrderStatus.SHIPPED:
            raise AppException(OrderError.INVALID_STATUS)

        now_iso = datetime.now(timezone.utc).isoformat()
        order.status = OrderStatus.COMPLETED
        order.completed_at = now_iso

        # 释放冻结佣金（payment 模式）或计算佣金（completion 模式）
        await self.commission_service.release_commissions(order)

        logger.info("order_completed", order_no=order.order_no)

    # --------------------------------------------------------------------------
    # 6. B 端发货
    # --------------------------------------------------------------------------
    async def ship_order(
        self,
        order_id: UUID,
        shipping_company: str,
        tracking_number: str,
    ) -> None:
        """管理员发货"""
        order = await self.repo.get_by_id(order_id)
        if not order:
            raise AppException(OrderError.NOT_FOUND)

        if order.status != OrderStatus.PENDING_SHIPMENT:
            raise AppException(OrderError.INVALID_STATUS)

        now_iso = datetime.now(timezone.utc).isoformat()
        order.status = OrderStatus.SHIPPED
        order.shipping_company = shipping_company
        order.tracking_number = tracking_number
        order.shipped_at = now_iso

        logger.info(
            "order_shipped",
            order_no=order.order_no,
            tracking=tracking_number,
        )

    # --------------------------------------------------------------------------
    # 7. 管理员强制取消（退款+扣回佣金）
    # --------------------------------------------------------------------------
    async def force_cancel(
        self,
        order_id: UUID,
        admin_id: UUID,
        cancel_reason: str,
    ) -> None:
        """管理员强制取消：退款 + 扣回佣金 + 释放库存"""
        from app.domains.payments.service import PaymentService

        order = await self.repo.get_by_id(order_id)
        if not order:
            raise AppException(OrderError.NOT_FOUND)

        if order.status not in (OrderStatus.PENDING_SHIPMENT, OrderStatus.SHIPPED):
            raise AppException(OrderError.INVALID_STATUS)

        # 1. 退款
        payment_svc = PaymentService(self.db)
        await payment_svc.refund_payment(order.id)

        # 2. 扣回佣金
        await self.commission_service.revoke_commissions(order)

        # 3. 释放库存（仅待发货状态，已发货的不恢复）
        if order.status == OrderStatus.PENDING_SHIPMENT:
            await self._restore_stock(order)

        # 4. 更新状态
        now_iso = datetime.now(timezone.utc).isoformat()
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = now_iso
        order.cancel_reason = cancel_reason
        order.cancelled_by = admin_id
        order.commission_total = Decimal("0.00")

        logger.info(
            "order_force_cancelled",
            order_no=order.order_no,
            admin_id=str(admin_id),
        )

    # --------------------------------------------------------------------------
    # 内部辅助
    # --------------------------------------------------------------------------
    async def _restore_stock(self, order: Order) -> None:
        """恢复订单中所有商品的库存"""
        from app.domains.products.repository import ProductRepository, ProductSkuRepository

        product_repo = ProductRepository(self.db)
        sku_repo = ProductSkuRepository(self.db)
        items = await self.repo.get_items(order.id)

        for item in items:
            if item.sku_id:
                await sku_repo.restore_stock(item.sku_id, item.quantity)
            else:
                await product_repo.restore_stock(item.product_id, item.quantity)
