"""
File: app/domains/admin/repository.py
Description: B端管理员领域仓储层 (Repository)

负责 SysAdmin / SysRole / SysPermission 的数据库访问操作。
采用与 UserRepository 相同的依赖风格：直接接受 AsyncSession 注入。

Author: jinmozhe
Created: 2026-04-12
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.admin import SysAdmin, SysRole


class AdminRepository:
    """
    管理员仓储类。
    直接持有 session 的轻量实现（适配现有项目中 BaseRepository 的风格）。
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_username(self, username: str) -> SysAdmin | None:
        """
        根据用户名查询激活的管理员账号，同时预加载其角色与权限（一次性批量查询）。
        使用 selectinload 避免 N+1 查询问题。
        """
        stmt = (
            select(SysAdmin)
            .where(SysAdmin.username == username, SysAdmin.is_active.is_(True))
            .options(
                # 预加载 roles 关联并进一步加载 roles 下的 permissions
                selectinload(SysAdmin.roles).selectinload(SysRole.permissions)
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_with_roles(self, admin_id: str) -> SysAdmin | None:
        """
        根据 ID 查询管理员（携带完整角色权限树），用于 /me 接口数据返回。
        """
        stmt = (
            select(SysAdmin)
            .where(SysAdmin.id == admin_id, SysAdmin.is_active.is_(True))
            .options(
                selectinload(SysAdmin.roles).selectinload(SysRole.permissions)
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
