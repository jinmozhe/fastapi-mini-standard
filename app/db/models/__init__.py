"""
File: app/db/models/__init__.py
Description: ORM 模型注册表

本模块负责：
1. 导入所有业务模型 (User 等)
2. 导入基类 (Base, UUIDModel, Mixins)
3. 导出它们供 Alembic (env.py) 自动发现 metadata

注意：
每当新增一个 Model 文件，必须在此处导入，
否则 Alembic autogenerate 无法检测到新表。

Author: jinmozhe
Created: 2025-11-25
"""

# 1. 导入基类与组件
from app.db.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDBase,
    UUIDModel,
)

# 2. 导入业务模型
# 注意：新增模型必须在此处导入，否则 Alembic 无法识别
from app.db.models.user import User
from app.db.models.admin import SysAdmin, SysRole, SysPermission
from app.db.models.log import LoginLog, AuditLog

# 未来新增模型示例:
# from app.db.models.user_profile import UserProfile
# from app.db.models.user_social import UserSocial
# from app.db.models.log import LoginLog, OperationLog

# 3. 显式导出 (供 Alembic 识别)
__all__ = [
    # 基类
    "Base",
    "UUIDBase",
    "UUIDModel",
    "TimestampMixin",
    "SoftDeleteMixin",
    # 业务模型
    "User",
    "SysAdmin",
    "SysRole",
    "SysPermission",
    "LoginLog",
    "AuditLog",
]
