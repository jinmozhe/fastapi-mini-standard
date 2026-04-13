"""
File: app/domains/payments/router.py
Description: 支付领域路由

接口说明：
- 微信支付回调通知：公开接口，微信服务器直接调用（不鉴权）
- 支付状态查询：C 端用户查看自己的支付状态（需鉴权）
- 发起支付 / 退款：不直接暴露路由，由订单域 Service 内部调用

关于"发起支付"为何不独立暴露路由：
  支付必须在订单上下文中发起（创建订单 → 锁库存 → 发起支付），
  单独暴露支付接口会导致无订单上下文的裸支付，产生安全风险。
  因此 initiate_payment() 只作为 Service 方法供订单域调用。

Author: jinmozhe
Created: 2026-04-13
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request

from app.api.deps import CurrentUser
from app.core.logging import logger
from app.core.response import ResponseModel
from app.domains.payments.dependencies import PaymentServiceDep
from app.domains.payments.schemas import PaymentRecordRead, WechatCallbackPayload

payment_router = APIRouter()


# ==============================================================================
# C 端：查询支付状态（前端轮询/跳转后查询）
# ==============================================================================

@payment_router.get(
    "/{payment_no}/status",
    response_model=ResponseModel[PaymentRecordRead],
    summary="查询支付状态",
)
async def get_payment_status(
    request: Request,
    payment_no: str,
    user: CurrentUser,
    service: PaymentServiceDep,
) -> ResponseModel[Any]:
    """
    根据支付流水号查询支付状态。
    前端在微信支付调起后轮询此接口判断支付是否完成。
    """
    from app.core.exceptions import AppException
    from app.domains.payments.constants import PaymentError

    record = await service.repo.get_by_payment_no(payment_no)
    if not record or record.user_id != user.id:
        raise AppException(PaymentError.NOT_FOUND)

    return ResponseModel.success(data=PaymentRecordRead.model_validate(record))


# ==============================================================================
# 微信支付回调通知（公开接口，不鉴权）
# ==============================================================================

@payment_router.post(
    "/wechat/notify",
    summary="微信支付回调通知",
    include_in_schema=False,  # 不在 OpenAPI 文档中展示（内部接口）
)
async def wechat_pay_notify(
    request: Request,
    service: PaymentServiceDep,
) -> dict:
    """
    微信支付结果通知接口。

    完整流程：
    1. 接收微信服务器的 POST 请求（JSON 格式）
    2. 用 API V3 密钥验签并解密 resource 字段
    3. 解析业务数据并调用 service.handle_wechat_callback()
    4. 返回 {"code": "SUCCESS"} 告知微信处理成功

    TODO: 正式对接时需实现 V3 签名验证和 AES-256-GCM 解密
    """
    try:
        # TODO: 正式环境需要验签 + 解密
        # raw_body = await request.body()
        # 1. 从 header 取签名: Wechatpay-Signature, Wechatpay-Timestamp, Wechatpay-Nonce
        # 2. 用微信平台公钥验证签名
        # 3. 用 API V3 Key 做 AES-256-GCM 解密 resource 字段
        # 4. 解密后得到明文 JSON

        body = await request.json()

        # 简化处理：假设 body 已经是解密后的业务数据
        # 正式环境这里需要先解密 body["resource"]["ciphertext"]
        payload = WechatCallbackPayload(**body)

        record = await service.handle_wechat_callback(payload)
        await service.db.commit()

        logger.info("wechat_notify_processed", payment_no=payload.out_trade_no, status=record.status)

        # 返回成功告知微信不再重试
        return {"code": "SUCCESS", "message": "OK"}

    except Exception as e:
        logger.error("wechat_notify_error", error=str(e))
        # 返回失败让微信重试
        return {"code": "FAIL", "message": str(e)}
