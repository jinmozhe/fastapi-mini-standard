"""
File: app/domains/referrals/schemas.py
Description: 推荐关系领域 Schema

Author: jinmozhe
Created: 2026-04-13
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# C 端
# ==============================================================================

class InviteCodeResult(BaseModel):
    """我的邀请码"""
    invite_code: str
    user_id: UUID


class InviterInfo(BaseModel):
    """我的推荐人信息"""
    user_id: UUID
    nickname: str | None
    avatar: str | None
    invited_at: str | None


class TeamMemberItem(BaseModel):
    """团队成员信息"""
    user_id: UUID
    nickname: str | None
    avatar: str | None
    mobile: str | None
    level_name: str | None
    total_consume: Decimal = Decimal("0.00")
    invited_at: str | None
    created_at: datetime | None


class TeamPageResult(BaseModel):
    """团队成员分页"""
    items: list[TeamMemberItem]
    total: int
    page: int
    page_size: int


class TeamStats(BaseModel):
    """团队统计"""
    first_level_count: int = Field(0, description="一级团队人数")
    second_level_count: int = Field(0, description="二级团队人数")
    third_level_count: int = Field(0, description="三级团队人数")
    total_count: int = Field(0, description="团队总人数")
    first_level_consume: Decimal = Field(Decimal("0.00"), description="一级团队总消费")
    second_level_consume: Decimal = Field(Decimal("0.00"), description="二级团队总消费")
    third_level_consume: Decimal = Field(Decimal("0.00"), description="三级团队总消费")


# ==============================================================================
# B 端
# ==============================================================================

class AdminBindReq(BaseModel):
    """管理员手动绑定推荐人"""
    user_id: UUID = Field(..., description="要绑定的用户")
    inviter_id: UUID = Field(..., description="推荐人用户 ID")


class AdminTeamResult(BaseModel):
    """管理员查看团队树"""
    user_id: UUID
    nickname: str | None
    first_level: list[TeamMemberItem]
    second_level: list[TeamMemberItem]
    third_level: list[TeamMemberItem]
    stats: TeamStats
