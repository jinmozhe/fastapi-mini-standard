"""
File: app/domains/users/dependencies.py
Description: 用户领域依赖注入 (DI)

本模块负责定义和组装用户领域的依赖项：
1. get_user_repository: 注入 DB 会话，实例化 Repository
2. get_user_service: 注入 Repository，实例化 Service

依赖链：
DBSession → UserRepository → UserService → UserServiceDep

Router 层将直接使用 UserServiceDep，无需关心底层细节。

Author: jinmozhe
Created: 2025-11-26
"""

from typing import Annotated

from fastapi import Depends

# 1. 导入全局 DBSession 别名 (注意没有空格)
from app.api.deps import DBSession
from app.db.models.user import User
from app.domains.users.repository import UserRepository
from app.domains.users.service import UserService


async def get_user_repository(session: DBSession) -> UserRepository:
    """
    获取用户仓储实例 (UserRepository)。
    使用全局 DBSession (Annotated[AsyncSession, ...]) 自动处理 DB 连接。
    """
    return UserRepository(model=User, session=session)


# 定义中间别名，方便下方函数使用 (可选，也可以直接写 Depends)
UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]


async def get_user_service(
    repo: UserRepoDep,  # 这里直接使用上面定义的别名，更简洁
) -> UserService:
    """
    获取用户服务实例 (UserService)。
    自动注入 UserRepository。
    """
    return UserService(repo=repo)


# ==============================================================================
# 导出类型别名，供 Router 层使用
# ==============================================================================

# Router 中只需写: service: UserServiceDep
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
