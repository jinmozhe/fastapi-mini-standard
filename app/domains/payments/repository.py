"""
File: app/domains/payments/repository.py
Description: 支付记录数据访问层

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.payment import PaymentRecord


class PaymentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, payment_id: UUID) -> Optional[PaymentRecord]:
        """按 ID 查支付记录"""
        stmt = select(PaymentRecord).where(PaymentRecord.id == payment_id)
        return await self.db.scalar(stmt)

    async def get_by_payment_no(self, payment_no: str) -> Optional[PaymentRecord]:
        """按支付流水号查支付记录（回调时使用）"""
        stmt = select(PaymentRecord).where(PaymentRecord.payment_no == payment_no)
        return await self.db.scalar(stmt)

    async def get_by_order_id(self, order_id: UUID) -> Optional[PaymentRecord]:
        """按订单 ID 查支付记录（一个订单只对应一条有效支付）"""
        stmt = (
            select(PaymentRecord)
            .where(PaymentRecord.order_id == order_id)
            .order_by(PaymentRecord.created_at.desc())
        )
        return await self.db.scalar(stmt)

    async def get_paid_by_order_id(self, order_id: UUID) -> Optional[PaymentRecord]:
        """获取订单关联的已支付记录（退款时使用）"""
        stmt = select(PaymentRecord).where(
            PaymentRecord.order_id == order_id,
            PaymentRecord.status == "paid",
        )
        return await self.db.scalar(stmt)
