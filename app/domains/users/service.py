"""
File: app/domains/users/service.py
Description: 用户领域服务 (业务逻辑层)

本模块封装用户管理的核心业务逻辑：
1. 用户查询：通过 ID 获取用户 (自动过滤软删除)。
2. 用户更新：处理密码哈希、变更唯一性校验。
3. 用户删除：软删除用户账户。
4. 异常处理：抛出业务特定的 AppException。

注意：
- 所有数据库写操作 (Update/Delete) 的事务提交 (Commit) 由本层负责。
- 密码哈希使用异步版本函数，避免阻塞事件循环。

Author: jinmozhe
Created: 2025-11-25
Updated: 2026-04-03 (移除 create 到 auth 域)
"""

from datetime import UTC, datetime
from uuid import UUID

from app.core.exceptions import AppException
from app.core.logging import logger
from app.core.security import get_password_hash_async
from app.db.models.user import User
from app.domains.users.constants import UserError
from app.domains.users.repository import UserRepository
from app.domains.users.schemas import UserUpdate


class UserService:
    """
    用户领域服务。

    职责：
    - 编排业务流程
    - 执行业务规则校验 (如：手机号是否重复)
    - 调用 Repository 进行数据持久化
    """

    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def get(self, user_id: UUID) -> User:
        """
        获取用户详情。
        如果用户不存在或已被软删除，抛出 AppException。
        """
        user = await self.repo.get(user_id)

        # 业务层要把"软删除"视为"不存在"
        if not user or user.is_deleted:
            raise AppException(UserError.NOT_FOUND)
        return user

    async def update(self, user_id: UUID, obj_in: UserUpdate) -> User:
        """
        更新用户信息 (支持密码修改和唯一性校验)。
        """
        user = await self.get(user_id)

        # 获取更新数据 (字典)
        update_data = obj_in.model_dump(exclude_unset=True)

        # 1. 处理密码修改 (特殊字段)
        new_password = update_data.pop("password", None)
        if new_password:
            hashed_password = await get_password_hash_async(new_password)
            user.hashed_password = hashed_password

        # 2. 处理唯一性字段变更 (防止冲突)
        has_mobile_change = "phone_code" in update_data or "mobile" in update_data
        
        if has_mobile_change:
            new_code = update_data.get("phone_code", user.phone_code)
            new_mobile = update_data.get("mobile", user.mobile)
            
            if new_code != user.phone_code or new_mobile != user.mobile:
                existing = await self.repo.get_by_mobile(new_code, new_mobile)
                if existing and existing.id != user.id:
                    raise AppException(UserError.PHONE_EXIST)

        if "email" in update_data and update_data["email"] != user.email:
            if update_data["email"] is not None:
                existing = await self.repo.get_by_email(update_data["email"])
                if existing and existing.id != user.id:
                    raise AppException(UserError.EMAIL_EXIST)

        if "username" in update_data and update_data["username"] != user.username:
            if update_data["username"] is not None:
                existing = await self.repo.get_by_username(update_data["username"])
                if existing and existing.id != user.id:
                    raise AppException(UserError.USERNAME_EXIST)

        # 3. 执行常规字段更新
        updated_user = await self.repo.update(user, update_data)

        # 4. 提交事务
        await self.repo.session.commit()
        await self.repo.session.refresh(updated_user)

        logger.bind(user_id=str(user_id)).info("User updated successfully")

        return updated_user

    async def delete(self, user_id: UUID) -> None:
        """
        删除用户 (软删除)。
        """
        user = await self.get(user_id)

        # 执行软删除
        user.is_deleted = True
        user.deleted_at = datetime.now(UTC)

        # 提交事务
        await self.repo.session.commit()

        logger.bind(user_id=str(user_id)).info("User deleted successfully")
