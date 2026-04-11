"""
File: app/db/models/admin.py
Description: B端中后台账号与经典的 RBAC 权限体系 ORM 模型

Author: jinmozhe
Created: 2026-04-12
"""

from typing import List

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import UUIDModel

# ------------------------------------------------------------------------------
# 关联中间表 (Many-to-Many Mapping Tables)
# 对于权限与角色绑定，直接使用物理表做级联是合理的，因为解绑员工权限不涉及业务历史的破坏
# ------------------------------------------------------------------------------

sys_admin_role_table = Table(
    "sys_admin_role",
    UUIDModel.metadata,
    Column("admin_id", ForeignKey("sys_admins.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("sys_roles.id", ondelete="CASCADE"), primary_key=True),
)

sys_role_permission_table = Table(
    "sys_role_permission",
    UUIDModel.metadata,
    Column("role_id", ForeignKey("sys_roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("sys_permissions.id", ondelete="CASCADE"), primary_key=True),
)


# ------------------------------------------------------------------------------
# 核心实体模型 (RBAC Entities)
# ------------------------------------------------------------------------------

class SysPermission(UUIDModel):
    """系统权限点表 (表示系统的最小特权单元)"""
    __tablename__ = "sys_permissions"

    code: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False, comment="权限标识串 (如: order:refund)"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="显示名称 (如: 订单退款)")
    type: Mapped[str] = mapped_column(String(20), nullable=False, comment="类型: menu|button|api")
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="父节点ID(用于构建菜单树)")

    __table_args__ = (
        CheckConstraint("type IN ('menu', 'button', 'api')", name="ck_sys_permission_type_valid"),
    )


class SysRole(UUIDModel):
    """角色表 (权限的打包集合)"""
    __tablename__ = "sys_roles"

    code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False, comment="角色编码 (如: FINANCE_MANAGER)"
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="显示名称 (如: 财务部经理)")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="描述")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")

    # 预留用于跨表查询其下属的 permission，以空间换取 SQL 编写的复杂度，并且此处理论上会用到 selectinload
    permissions: Mapped[List["SysPermission"]] = relationship(
        "SysPermission", 
        secondary=sys_role_permission_table, 
        lazy="noload"
    )


class SysAdmin(UUIDModel):
    """管理员账号表 (B端内部员工体系)"""
    __tablename__ = "sys_admins"

    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False, comment="管理后台登录名"
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False, comment="Argon2 密码哈希")
    real_name: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="内部真名/花名")
    
    # 不设 default，强制开发者业务流传值实现 Fail Fast
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, comment="是否激活")

    # 身份权限这种涉及多对多跨级强检索的场景，允许开放 ORM 聚合关系方便框架启动拦截器查询
    roles: Mapped[List["SysRole"]] = relationship(
        "SysRole", 
        secondary=sys_admin_role_table, 
        lazy="noload"
    )
