"""
File: app/db/models/log.py
Description: 系统核心安全审计日志表 (LoginLog, AuditLog)

Author: jinmozhe
Created: 2026-04-12
"""

from sqlalchemy import Boolean, CheckConstraint, Index, String, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import UUIDModel


class LoginLog(UUIDModel):
    """
    统一视图的登录追踪日志。
    涵盖 B端与 C端所有身份网关的异常拦截和登录记录，用于撞库分析与业务维权诊断。
    """
    __tablename__ = "sys_login_logs"

    # 执行者身份 ("user" 或 "admin")
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="身份集: user|admin")
    
    # 账号实体的主键（如果用户名输错了导致库内查无此人，则此项为 NULL，形成孤立的撞库记录）
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="目标标识")
    
    # 来源网域
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="来源IP")
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="请求端指纹")
    
    # 核心拦截判定
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, comment="是否发放 Token 成功")
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="判定明细(如: 密码错误, CAPTCHA拦截)")

    __table_args__ = (
        CheckConstraint("actor_type IN ('user', 'admin')", name="ck_loginlog_actortype_valid"),
        # 高频查询：运维最常通过人查他某天为何没进来，所以建立联合索引
        Index("ix_loginlog_actor_status", "actor_id", "status"),
    )


class AuditLog(UUIDModel):
    """
    高级操作防内鬼审计记录。
    专用于记录拥有破坏权限的管理员执行的高危行为及参数。
    """
    __tablename__ = "sys_audit_logs"

    # 执行者身份
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="身份集: user|admin")
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="目标标识")

    # 接口元数据链
    module: Mapped[str] = mapped_column(String(50), nullable=False, comment="操作模块 (如: finance)")
    action: Mapped[str] = mapped_column(String(100), nullable=False, comment="核心动词 (如: refund)")
    
    endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="网络层:API端点")
    method: Mapped[str | None] = mapped_column(String(10), nullable=True, comment="网络层:请求方法")
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="发起者IP")
    
    # 【高能预警】JSONB 落库：极其重要，这是一个防篡改的黑匣子，封印案发时他向服务器传入的所有重要参数快照！
    request_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="请求快照包裹")
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="服务器返回响应码")

    __table_args__ = (
        CheckConstraint("actor_type IN ('user', 'admin')", name="ck_auditlog_actortype_valid"),
        # 防止存入非法数值，强迫结构化分析
        CheckConstraint(
            "request_payload IS NULL OR jsonb_typeof(request_payload) = 'object' OR jsonb_typeof(request_payload) = 'array'",
            name="ck_auditlog_payload_valid"
        ),
        # 便于按模块分类大盘排查
        Index("ix_auditlog_module_action", "module", "action"),
    )
