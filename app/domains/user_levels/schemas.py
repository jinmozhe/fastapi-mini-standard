"""
File: app/domains/user_levels/schemas.py
Description: 用户等级领域数据模型 (Pydantic Schema)

包含 B端管理接口和 C端展示接口的请求/响应契约。

Author: jinmozhe
Created: 2026-04-12
"""

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 1. B端请求模型 (Admin Request Schemas)
# ==============================================================================


class UserLevelCreateRequest(BaseModel):
    """创建会员等级请求"""

    name: str = Field(..., min_length=1, max_length=50, description="等级名称")
    rank_weight: int = Field(..., ge=1, description="等级排序权重 (越大越高)")
    discount_rate: Decimal = Field(
        default=Decimal("1.0000"), ge=0, le=1, description="折扣率 (如 0.95 = 95折)"
    )
    upgrade_rules: dict[str, Any] | None = Field(
        None, description="升级规则 (JSONB AST 规则树)"
    )
    commission_rules: list[dict[str, Any]] | None = Field(
        None, description="分佣规则 [{'rank':1,'first':'3%','second':'2%','other':'0'}]"
    )
    reward_rules: list[dict[str, Any]] | None = Field(
        None, description="升级奖励规则 [{'rank':2,'first':'100','second':'50','other':'0'}]"
    )
    icon_url: str | None = Field(None, max_length=500, description="等级图标 URL")
    description: str | None = Field(None, description="等级权益说明 (富文本)")
    is_active: bool = Field(default=True, description="是否启用")


class UserLevelUpdateRequest(BaseModel):
    """更新会员等级请求 (所有字段可选)"""

    name: str | None = Field(None, min_length=1, max_length=50, description="等级名称")
    rank_weight: int | None = Field(None, ge=1, description="等级排序权重")
    discount_rate: Decimal | None = Field(
        None, ge=0, le=1, description="折扣率"
    )
    upgrade_rules: dict[str, Any] | None = Field(
        None, description="升级规则 (JSONB AST 规则树)"
    )
    commission_rules: list[dict[str, Any]] | None = Field(
        None, description="分佣规则"
    )
    reward_rules: list[dict[str, Any]] | None = Field(
        None, description="升级奖励规则"
    )
    icon_url: str | None = Field(None, max_length=500, description="等级图标 URL")
    description: str | None = Field(None, description="等级权益说明")
    is_active: bool | None = Field(None, description="是否启用")


class UserLevelOverrideRequest(BaseModel):
    """人工强制指定用户等级"""

    level_id: uuid.UUID = Field(..., description="目标等级 ID")
    remark: str | None = Field(None, max_length=500, description="操作备注")


# ==============================================================================
# 2. 响应模型 (Response Schemas)
# ==============================================================================


class UserLevelOut(BaseModel):
    """等级详情输出 (B端完整版)"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="等级 ID")
    name: str = Field(..., description="等级名称")
    rank_weight: int = Field(..., description="等级排序权重")
    discount_rate: Decimal = Field(..., description="折扣率")
    upgrade_rules: dict[str, Any] | None = Field(None, description="升级规则")
    commission_rules: list[dict[str, Any]] | None = Field(None, description="分佣规则")
    reward_rules: list[dict[str, Any]] | None = Field(None, description="升级奖励规则")
    icon_url: str | None = Field(None, description="等级图标 URL")
    description: str | None = Field(None, description="等级权益说明")
    is_active: bool = Field(..., description="是否启用")


class UserLevelPublicOut(BaseModel):
    """等级详情输出 (C端脱敏版，隐藏分佣/奖励规则)"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="等级 ID")
    name: str = Field(..., description="等级名称")
    rank_weight: int = Field(..., description="等级排序权重")
    discount_rate: Decimal = Field(..., description="折扣率")
    icon_url: str | None = Field(None, description="等级图标 URL")
    description: str | None = Field(None, description="等级权益说明")


class UserLevelProfileOut(BaseModel):
    """用户等级档案输出 (聚合到 /users/me)"""

    model_config = ConfigDict(from_attributes=True)

    level_name: str | None = Field(None, description="当前等级名称")
    level_rank: int | None = Field(None, description="当前等级权重")
    discount_rate: Decimal | None = Field(None, description="当前折扣率")
    icon_url: str | None = Field(None, description="等级图标")
    is_manual: bool = Field(default=False, description="是否人工锁定")
    total_consume: Decimal = Field(default=Decimal("0"), description="累计消费金额")
    total_points: int = Field(default=0, description="累计积分")
    total_buy_number: int = Field(default=0, description="累计订单数")
    total_invite_number: int = Field(default=0, description="累计邀请人数")


class UserLevelRecordOut(BaseModel):
    """升降级历史记录输出"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="记录 ID")
    change_type: str = Field(..., description="变动类型: UPGRADE/DOWNGRADE/MANUAL")
    remark: str | None = Field(None, description="变动说明")
