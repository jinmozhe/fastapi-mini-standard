"""
File: app/domains/payments/service.py
Description: 支付领域核心业务逻辑

支付流程：
1. 余额支付：即时扣减钱包余额 → 记录支付流水 → 返回支付完成
2. 微信支付：调用微信统一下单API → 记录待支付流水 → 返回前端调起参数
3. 微信回调：验签解密 → 更新支付状态 → 通知订单域（TODO）

设计原则：
- 支付域只管收钱/退钱，不关心订单状态转换
- 订单域通过调用 PaymentService 的方法来驱动支付
- 微信支付走旁路开关（WECHAT_PAY_ENABLE），关闭时返回模拟数据

Author: jinmozhe
Created: 2026-04-13
"""

import time
import uuid as uuid_mod
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import logger
from app.db.models.payment import PaymentRecord
from app.domains.payments.constants import (
    VALID_PAYMENT_METHODS,
    PaymentError,
    PaymentMethod,
    PaymentStatus,
)
from app.domains.payments.repository import PaymentRepository
from app.domains.payments.schemas import (
    PaymentCreateInternal,
    PaymentInitResult,
    WechatCallbackPayload,
    WechatPayParams,
)
from app.domains.user_wallets.constants import BalanceChangeType


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PaymentRepository(db)

    # --------------------------------------------------------------------------
    # 支付流水号生成（PAY + 年月日时分秒 + 6位随机数 = 23字符，≤32）
    # --------------------------------------------------------------------------
    @staticmethod
    def _generate_payment_no() -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        rand = str(uuid_mod.uuid4().int)[:6]
        return f"PAY{ts}{rand}"

    # --------------------------------------------------------------------------
    # 核心方法：发起支付（供订单域调用）
    # --------------------------------------------------------------------------
    async def initiate_payment(
        self,
        data: PaymentCreateInternal,
        openid: str | None = None,
    ) -> PaymentInitResult:
        """
        发起支付。

        余额支付：即时扣减 → 状态直接置为 paid
        微信支付：调统一下单 → 状态为 pending → 返回前端调起参数

        参数:
            data: 支付创建内部请求
            openid: 微信用户 openid（微信支付必须）
        """
        if data.payment_method not in VALID_PAYMENT_METHODS:
            raise AppException(PaymentError.INVALID_METHOD)

        # 检查是否已有该订单的支付记录
        existing = await self.repo.get_by_order_id(data.order_id)
        if existing and existing.status == PaymentStatus.PAID:
            raise AppException(PaymentError.ALREADY_PAID)

        # 生成支付流水号
        payment_no = self._generate_payment_no()

        if data.payment_method == PaymentMethod.BALANCE:
            return await self._pay_by_balance(data, payment_no)
        else:
            return await self._pay_by_wechat(data, payment_no, openid)

    # --------------------------------------------------------------------------
    # 余额支付
    # --------------------------------------------------------------------------
    async def _pay_by_balance(
        self,
        data: PaymentCreateInternal,
        payment_no: str,
    ) -> PaymentInitResult:
        """余额支付：即时扣减钱包余额"""
        from app.domains.user_wallets.service import UserWalletService

        wallet_service = UserWalletService(self.db)

        # 检查余额是否充足
        wallet = await wallet_service.get_or_create_wallet(data.user_id)
        if wallet.balance < data.amount:
            raise AppException(PaymentError.INSUFFICIENT_BALANCE)

        # 扣减余额（内部带乐观锁 + 流水记录）
        await wallet_service.change_balance(
            user_id=data.user_id,
            amount_delta=-data.amount,
            change_type=BalanceChangeType.ORDER_PAY,
            ref_id=data.order_id,
            remark=f"订单支付 {payment_no}",
        )

        now_iso = datetime.now(timezone.utc).isoformat()

        # 创建已完成的支付记录
        record = PaymentRecord(
            payment_no=payment_no,
            order_id=data.order_id,
            user_id=data.user_id,
            payment_method=PaymentMethod.BALANCE,
            amount=data.amount,
            status=PaymentStatus.PAID,
            paid_at=now_iso,
        )
        self.db.add(record)

        logger.info(
            "payment_balance_success",
            payment_no=payment_no,
            user_id=str(data.user_id),
            amount=str(data.amount),
        )

        return PaymentInitResult(
            payment_no=payment_no,
            payment_method=PaymentMethod.BALANCE,
            amount=data.amount,
            status=PaymentStatus.PAID,
            wechat_pay_params=None,
        )

    # --------------------------------------------------------------------------
    # 微信支付
    # --------------------------------------------------------------------------
    async def _pay_by_wechat(
        self,
        data: PaymentCreateInternal,
        payment_no: str,
        openid: str | None,
    ) -> PaymentInitResult:
        """
        微信支付：调用统一下单 API 获取 prepay_id

        当 WECHAT_PAY_ENABLE = False 时，返回模拟数据（开发调试用）。
        """
        if not settings.WECHAT_PAY_ENABLE:
            # ====== 旁路模式：模拟返回 ======
            logger.warning(
                "wechat_pay_bypass_mode",
                payment_no=payment_no,
                msg="WECHAT_PAY_ENABLE=False, returning mock data",
            )

            mock_prepay_id = f"mock_prepay_{payment_no}"
            record = PaymentRecord(
                payment_no=payment_no,
                order_id=data.order_id,
                user_id=data.user_id,
                payment_method=PaymentMethod.WECHAT,
                amount=data.amount,
                status=PaymentStatus.PENDING,
                wechat_prepay_id=mock_prepay_id,
            )
            self.db.add(record)

            return PaymentInitResult(
                payment_no=payment_no,
                payment_method=PaymentMethod.WECHAT,
                amount=data.amount,
                status=PaymentStatus.PENDING,
                wechat_pay_params=WechatPayParams(
                    appId=settings.WECHAT_MINI_APP_ID or "wx_mock_app_id",
                    timeStamp=str(int(time.time())),
                    nonceStr=uuid_mod.uuid4().hex[:32],
                    package=f"prepay_id={mock_prepay_id}",
                    signType="RSA",
                    paySign="mock_sign_for_development",
                ),
            )

        # ====== 正式模式：调用微信支付 V3 统一下单 ======
        # TODO: 实际对接微信支付 JSAPI
        # 1. 读取商户私钥 → 构造请求签名
        # 2. POST https://api.mch.weixin.qq.com/v3/pay/transactions/jsapi
        # 3. 解析响应取 prepay_id
        # 4. 用 prepay_id 构造前端调起参数并签名
        #
        # 实际对接时需要安装 wechatpayv3 库 或 手动 httpx + RSA 签名
        # 此处保留骨架，实际代码在部署前完善

        raise AppException(
            PaymentError.WECHAT_PAY_FAILED,
            message="微信支付正式接口暂未对接，请在 .env 中设置 WECHAT_PAY_ENABLE=false 使用模拟模式",
        )

    # --------------------------------------------------------------------------
    # 微信支付回调处理
    # --------------------------------------------------------------------------
    async def handle_wechat_callback(
        self,
        payload: WechatCallbackPayload,
    ) -> PaymentRecord:
        """
        处理微信支付结果回调。

        调用流程：
        1. Router 层接收原始回调 → 验签解密 → 构造 WechatCallbackPayload
        2. 调用本方法更新支付状态
        3. Router 层返回 200 给微信服务器

        TODO: 回调后应通知订单域更新订单状态
        """
        record = await self.repo.get_by_payment_no(payload.out_trade_no)
        if not record:
            logger.error("wechat_callback_payment_not_found", payment_no=payload.out_trade_no)
            raise AppException(PaymentError.NOT_FOUND)

        if record.status == PaymentStatus.PAID:
            # 幂等性：重复回调直接返回
            logger.info("wechat_callback_duplicate", payment_no=payload.out_trade_no)
            return record

        if record.status != PaymentStatus.PENDING:
            logger.warning(
                "wechat_callback_invalid_status",
                payment_no=payload.out_trade_no,
                current_status=record.status,
            )
            raise AppException(PaymentError.INVALID_STATUS)

        if payload.trade_state == "SUCCESS":
            record.status = PaymentStatus.PAID
            record.wechat_transaction_id = payload.transaction_id
            record.paid_at = payload.success_time or datetime.now(timezone.utc).isoformat()

            logger.info(
                "payment_wechat_success",
                payment_no=payload.out_trade_no,
                transaction_id=payload.transaction_id,
            )
        else:
            # 非成功状态（CLOSED / PAYERROR 等）
            record.status = PaymentStatus.CLOSED
            record.remark = f"微信回调状态: {payload.trade_state}"

            logger.warning(
                "payment_wechat_failed",
                payment_no=payload.out_trade_no,
                trade_state=payload.trade_state,
            )

        return record

    # --------------------------------------------------------------------------
    # 关闭支付（超时未支付 / 用户取消）
    # --------------------------------------------------------------------------
    async def close_payment(self, order_id: UUID) -> None:
        """关闭订单关联的待支付记录"""
        record = await self.repo.get_by_order_id(order_id)
        if not record:
            return

        if record.status == PaymentStatus.PENDING:
            record.status = PaymentStatus.CLOSED
            record.remark = "订单超时/用户取消，支付关闭"
            logger.info("payment_closed", payment_no=record.payment_no, order_id=str(order_id))

    # --------------------------------------------------------------------------
    # 退款（供订单域调用）
    # --------------------------------------------------------------------------
    async def refund_payment(
        self,
        order_id: UUID,
        refund_amount: Decimal | None = None,
    ) -> PaymentRecord:
        """
        发起退款。

        余额支付：直接将金额退回钱包余额
        微信支付：TODO 调用微信退款 API

        参数:
            order_id: 订单 ID
            refund_amount: 退款金额（None = 全额退款）
        """
        record = await self.repo.get_paid_by_order_id(order_id)
        if not record:
            raise AppException(PaymentError.NOT_FOUND)

        actual_refund = refund_amount or record.amount
        if actual_refund > record.amount:
            raise AppException(PaymentError.REFUND_AMOUNT_EXCEEDED)

        now_iso = datetime.now(timezone.utc).isoformat()

        if record.payment_method == PaymentMethod.BALANCE:
            # 余额退款：直接充回钱包
            from app.domains.user_wallets.constants import BalanceChangeType
            from app.domains.user_wallets.service import UserWalletService

            wallet_service = UserWalletService(self.db)
            await wallet_service.change_balance(
                user_id=record.user_id,
                amount_delta=actual_refund,
                change_type=BalanceChangeType.ORDER_REFUND,
                ref_id=order_id,
                remark=f"订单退款 {record.payment_no}",
            )
            record.status = PaymentStatus.REFUNDED
            record.refund_amount = actual_refund
            record.refunded_at = now_iso

            logger.info(
                "payment_balance_refunded",
                payment_no=record.payment_no,
                refund_amount=str(actual_refund),
            )

        elif record.payment_method == PaymentMethod.WECHAT:
            # TODO: 调用微信退款 API
            # POST https://api.mch.weixin.qq.com/v3/refund/domestic/refunds
            record.status = PaymentStatus.REFUNDING
            record.refund_amount = actual_refund
            record.remark = "退款已发起，等待微信处理"

            logger.info(
                "payment_wechat_refund_initiated",
                payment_no=record.payment_no,
                refund_amount=str(actual_refund),
            )

        return record
