"""
File: app/api/deps.py
Description: 全局依赖注入定义 (DB Session + Authentication)

本模块负责：
1. 数据库会话管理 (get_db / DBSession)
2. JWT 鉴权与用户身份提取 (get_current_user / CurrentUser)
3. 权限控制 (get_current_superuser / SuperUser)

Author: jinmozhe
Created: 2025-12-05
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header
import jwt
from jwt.exceptions import PyJWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.error_code import SystemErrorCode
from app.core.exceptions import AppException
from app.db.models.user import User
from app.db.session import AsyncSessionLocal

# ------------------------------------------------------------------------------
# 1. Database Dependencies
# ------------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取异步数据库会话依赖。
    使用 async with 确保请求结束时自动关闭 session。
    """
    async with AsyncSessionLocal() as session:
        yield session


# 数据库会话依赖类型别名
DBSession = Annotated[AsyncSession, Depends(get_db)]


# ------------------------------------------------------------------------------
# 2. Authentication Dependencies (JWT 鉴权)
# ------------------------------------------------------------------------------


async def get_token_from_header(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """
    从 Authorization Header 提取 Bearer Token。
    格式要求: Authorization: Bearer <token>
    """
    if not authorization:
        raise AppException(SystemErrorCode.UNAUTHORIZED, message="Missing Authorization Header")

    scheme, _, param = authorization.partition(" ")
    if scheme.lower() != "bearer" or not param:
        raise AppException(SystemErrorCode.UNAUTHORIZED, message="Invalid Authentication Scheme")

    return param


async def get_current_user(
    token: Annotated[str, Depends(get_token_from_header)],
    session: DBSession,
) -> User:
    """
    解析 JWT 并获取当前登录用户。

    流程:
    1. 校验 JWT 签名与有效期 (jose.jwt.decode)
    2. 提取 sub (user_id)
    3. 查库校验用户是否存在、是否激活、是否软删除
    """
    # 1. JWT 解析与验签
    try:
        # Pylance 可能会报 secret_key 可能为 None，但我们在 config.py 中已有校验
        # 这里使用 settings.SECRET_KEY 是安全的
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,  # type: ignore[arg-type]
            algorithms=[settings.ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise AppException(SystemErrorCode.UNAUTHORIZED, message="Invalid Token: missing sub")
    except PyJWTError:
        # 签名错误或过期
        # 使用 from None 截断异常链，避免暴露底层 jose 异常细节
        raise AppException(SystemErrorCode.UNAUTHORIZED, message="Invalid Token or Expired") from None

    # 2. 查库确认用户状态
    # 即使 Token 未过期，如果用户被封号或删除，也应拒绝访问
    user = await session.get(User, user_id)

    if not user:
        raise AppException(SystemErrorCode.UNAUTHORIZED, message="User not found")

    if user.is_deleted:
        raise AppException(SystemErrorCode.UNAUTHORIZED, message="User has been deleted")

    if not user.is_active:
        raise AppException(SystemErrorCode.UNAUTHORIZED, message="User is inactive")

    return user


# ------------------------------------------------------------------------------
# 3. Permission Dependencies (权限控制)
# ------------------------------------------------------------------------------

# 已登录用户依赖
# 用法: async def endpoint(user: CurrentUser): ...
CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_superuser(current_user: CurrentUser) -> User:
    """
    超级管理员权限校验。
    """
    if not current_user.is_superuser:
        raise AppException(SystemErrorCode.FORBIDDEN, message="Not enough privileges")
    return current_user


# 超级管理员依赖
SuperUser = Annotated[User, Depends(get_current_superuser)]
