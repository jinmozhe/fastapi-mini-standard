"""
File: app/domains/users/repository.py
Description: 用户领域仓储层 (Repository)

本模块负责用户数据的数据库访问，继承自通用 BaseRepository。
扩展功能：
1. get_by_phone_number: 根据手机号查询 (自动过滤软删除)
2. get_by_email: 根据邮箱查询 (自动过滤软删除)
3. get_by_username: 根据用户名查询 (自动过滤软删除)

Author: jinmozhe
Created: 2025-11-25
"""

from typing import Sequence

from pydantic import BaseModel
from sqlalchemy import select, func, or_

from app.db.models.user import User
from app.db.repositories.base import BaseRepository
from app.domains.users.schemas import UserUpdate


class UserRepository(BaseRepository[User, BaseModel, UserUpdate]):
    """
    用户仓储类。
    继承了 BaseRepository 的 create/update/get/delete 方法。

    注意：
    本类中的查询方法默认都会过滤掉软删除的数据 (is_deleted=True)。
    如果业务场景需要查询"已注销"用户，请另行实现类似 get_with_deleted_by_xxx 的方法。
    """

    async def get_by_phone_number(self, phone_number: str) -> User | None:
        """
        根据手机号查询有效用户。
        """
        stmt = select(User).where(
            User.phone_number == phone_number, User.is_deleted.is_(False)
        )
        # 使用 scalar_one_or_none 以确保数据唯一性 (如果有脏数据导致多条，会抛错)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """
        根据邮箱查询有效用户。
        """
        stmt = select(User).where(User.email == email, User.is_deleted.is_(False))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """
        根据用户名查询有效用户。
        """
        stmt = select(User).where(User.username == username, User.is_deleted.is_(False))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 10,
        keyword: str | None = None
    ) -> tuple[Sequence[User], int]:
        """
        分页查询多条记录。支持根据手机号或用户名模糊搜索。
        """
        stmt = select(User).where(User.is_deleted.is_(False))
        if keyword:
            stmt = stmt.where(
                or_(
                    User.phone_number.icontains(keyword),
                    User.username.icontains(keyword),
                )
            )
            
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.session.scalar(count_stmt) or 0
        
        stmt = stmt.order_by(User.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all(), total
