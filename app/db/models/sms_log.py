"""
File: app/db/models/sms_log.py
Description: 短信发送记录模型 (审计级铁账本)

每一条短信的发送都必须留下不可篡改的记录，用于：
1. 运营对账：按月统计各模板发送量和费用
2. 风控审计：检测异常高频发送行为
3. 问题排查：用户反馈未收到验证码时，用 request_id 去云平台反查

Author: jinmozhe
Created: 2026-04-12
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.db.models.base import UUIDModel


class SmsLog(UUIDModel):
    """
    短信发送记录表 (永久审计日志)

    关键设计：
    - 不关联 users 外键：因为发送验证码时用户可能尚未注册
    - request_id 存储云平台流水号，用于和腾讯云 SMS 控制台对账
    - status 记录发送结果，便于统计成功率
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "sms_logs"

    # --------------------------------------------------------------------------
    # 必填字段：每条短信记录的基本信息
    # --------------------------------------------------------------------------

    # 手机区号
    phone_code: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="手机区号 (如 +86)"
    )

    # 手机号
    mobile: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, comment="手机号码"
    )

    # 短信用途类型 (login / register / reset_password / bind_phone)
    sms_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True, comment="短信用途类型"
    )

    # 发送状态 (success / failed / pending)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", comment="发送状态"
    )

    # 发送商标识 (tencent / aliyun)
    provider: Mapped[str] = mapped_column(
        String(20), nullable=False, default="tencent", comment="短信服务商"
    )

    # --------------------------------------------------------------------------
    # 选填字段：追踪与审计
    # --------------------------------------------------------------------------

    # 使用的模板 ID
    template_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="短信模板 ID"
    )

    # 实际发送的内容摘要（部分平台回调时返回）
    content: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="发送内容摘要"
    )

    # 云平台返回的请求流水号（对账用）
    request_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="云平台请求流水号"
    )

    # 发送失败原因
    fail_reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="失败原因"
    )

    # 请求方 IP（风控审计）
    ip_address: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="请求方 IP"
    )
