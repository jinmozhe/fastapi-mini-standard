"""
File: app/domains/payments/schemas.py
Description: 支付领域输入/输出验证模型

Author: jinmozhe
Created: 2026-04-13
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 发起支付（供订单域调用）
# ==============================================================================

class PaymentCreateInternal(BaseModel):
    """
    内部支付创建请求（由订单 Service 构造，不直接对外暴露）

    订单域调用 PaymentService.initiate_payment() 时传入此对象。
    """
    order_id: UUID = Field(..., description="关联订单 ID")
    user_id: UUID = Field(..., description="支付用户 ID")
    amount: Decimal = Field(..., gt=0, description="支付金额")
    payment_method: str = Field(..., description="支付方式: wechat / balance")


# ==============================================================================
# 微信支付前端调起参数
# ==============================================================================

class WechatPayParams(BaseModel):
    """
    微信小程序前端调起支付所需的参数包

    前端拿到后直接传入 wx.requestPayment(params)
    """
    appId: str = Field(..., description="小程序 AppID")
    timeStamp: str = Field(..., description="时间戳(秒)")
    nonceStr: str = Field(..., description="随机字符串")
    package: str = Field(..., description="统一下单接口返回的 prepay_id")
    signType: str = Field(default="RSA", description="签名类型")
    paySign: str = Field(..., description="签名")


# ==============================================================================
# 支付发起响应
# ==============================================================================

class PaymentInitResult(BaseModel):
    """支付发起结果"""
    payment_no: str = Field(..., description="支付流水号")
    payment_method: str = Field(..., description="支付方式")
    amount: Decimal = Field(..., description="支付金额")
    status: str = Field(..., description="支付状态")
    # 微信支付时返回前端调起参数，余额支付时为 None（已即时完成）
    wechat_pay_params: WechatPayParams | None = Field(
        default=None, description="微信支付调起参数（余额支付时为空）"
    )


# ==============================================================================
# 支付记录查询响应
# ==============================================================================

class PaymentRecordRead(BaseModel):
    """支付记录响应"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    payment_no: str
    order_id: UUID
    user_id: UUID
    payment_method: str
    amount: Decimal
    status: str
    wechat_transaction_id: str | None
    paid_at: str | None
    refund_amount: Decimal | None
    refunded_at: str | None
    remark: str | None
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# 微信支付回调通知（简化版骨架）
# ==============================================================================

class WechatCallbackPayload(BaseModel):
    """微信支付回调通知解密后的业务数据（V3 API）"""
    out_trade_no: str = Field(..., description="商户订单号（即 payment_no）")
    transaction_id: str = Field(..., description="微信支付订单号")
    trade_state: str = Field(..., description="交易状态: SUCCESS/CLOSED 等")
    success_time: str | None = Field(default=None, description="支付成功时间")
