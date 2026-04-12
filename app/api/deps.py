"""
File: app/api/deps.py
Description: 全局依赖注入定义 (DB Session + Authentication)

本模块负责：
1. 数据库会话管理 (get_db / DBSession)
2. C端 JWT 鉴权与用户身份提取 (get_current_user / CurrentUser)
3. B端管理员 JWT 鉴权 (get_current_admin / CurrentAdmin)
4. RBAC 权限校验工厂函数 (require_permission)

Author: jinmozhe
Created: 2025-12-05
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header
import jwt
from jwt.exceptions import PyJWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.error_code import SystemErrorCode
from app.core.exceptions import AppException
from app.db.models.admin import SysAdmin, SysRole
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
# 2. C端认证依赖 (JWT 鉴权 - 前台买家)
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
    解析 C端 JWT 并获取当前登录买家用户。

    流程:
    1. 校验 JWT 签名与有效期
    2. 验证 aud 字段不为 'backend'（拒绝 B端 Token 访问 C端接口）
    3. 查库校验用户状态
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,  # type: ignore[arg-type]
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False},  # aud 由我们手动校验
        )
        # 防止 B 端管理员 Token 被拿来访问 C 端接口
        if payload.get("aud") == "backend":
            raise AppException(SystemErrorCode.UNAUTHORIZED, message="B端凭证禁止访问C端接口")

        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise AppException(SystemErrorCode.UNAUTHORIZED, message="Invalid Token: missing sub")
    except PyJWTError:
        raise AppException(SystemErrorCode.UNAUTHORIZED, message="Invalid Token or Expired") from None

    user = await session.get(User, user_id)

    if not user:
        raise AppException(SystemErrorCode.UNAUTHORIZED, message="User not found")
    if user.is_deleted:
        raise AppException(SystemErrorCode.UNAUTHORIZED, message="User has been deleted")
    if not user.is_active:
        raise AppException(SystemErrorCode.UNAUTHORIZED, message="User is inactive")

    return user


# C端已登录用户依赖
# 用法: async def endpoint(user: CurrentUser): ...
CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_current_user(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db),
) -> User | None:
    """
    可选的 C 端用户依赖。
    如果客户端没传 Token 或 Token 失效，不抛错，静默返回 None。
    """
    if not authorization:
        return None

    scheme, _, param = authorization.partition(" ")
    if scheme.lower() != "bearer" or not param:
        return None

    try:
        payload = jwt.decode(
            param,
            settings.SECRET_KEY, # type: ignore
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False},
        )
        if payload.get("aud") == "backend":
            return None

        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
            
        user = await session.get(User, user_id_str)
        if user and not user.is_deleted and user.is_active:
            return user
    except PyJWTError:
        pass

    return None

OptionalCurrentUser = Annotated[User | None, Depends(get_optional_current_user)]


# ------------------------------------------------------------------------------
# 3. B端管理员认证依赖 (JWT 鉴权 - 后台管理员)
# ------------------------------------------------------------------------------


async def get_current_admin(
    token: Annotated[str, Depends(get_token_from_header)],
    session: DBSession,
) -> SysAdmin:
    """
    解析 B端 JWT 并获取当前登录管理员（含角色权限树预加载）。

    流程:
    1. 校验 JWT 签名与有效期
    2. 验证 aud='backend'（仅接受 B端专属 Token）
    3. 查库预加载角色权限，以供后续权限校验使用
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,  # type: ignore[arg-type]
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False},  # aud 由我们手动校验
        )
        # 必须携带 B端专属标识
        if payload.get("aud") != "backend":
            raise AppException(SystemErrorCode.UNAUTHORIZED, message="仅Backend凭证可访问管理接口")

        admin_id: str | None = payload.get("sub")
        if admin_id is None:
            raise AppException(SystemErrorCode.UNAUTHORIZED, message="Invalid Token: missing sub")
    except PyJWTError:
        raise AppException(SystemErrorCode.UNAUTHORIZED, message="Invalid Token or Expired") from None

    # 一次性预加载角色 + 权限（避免后续 N+1 查询）
    stmt = (
        select(SysAdmin)
        .where(SysAdmin.id == admin_id, SysAdmin.is_active.is_(True))
        .options(selectinload(SysAdmin.roles).selectinload(SysRole.permissions))
    )
    result = await session.execute(stmt)
    admin = result.scalar_one_or_none()

    if not admin:
        raise AppException(SystemErrorCode.UNAUTHORIZED, message="Admin not found or inactive")

    return admin


# B端管理员依赖
# 用法: async def endpoint(admin: CurrentAdmin): ...
CurrentAdmin = Annotated[SysAdmin, Depends(get_current_admin)]


# ------------------------------------------------------------------------------
# 4. RBAC 权限校验工厂 (精细化权限门卫)
# ------------------------------------------------------------------------------


def require_permission(permission_code: str):
    """
    RBAC 权限校验依赖工厂函数。

    用法示例:
        @router.post("/orders/{id}/refund")
        async def refund_order(
            admin: CurrentAdmin,
            _: None = Depends(require_permission("order:refund")),
        ):
            ...

    工作原理:
    1. 从 CurrentAdmin 中提取其所有角色的权限码集合
    2. 判断 permission_code 是否在其中
    3. 若不在则抛 FORBIDDEN，精确告知缺少的权限码

    Args:
        permission_code: 所需权限标识，如 "order:refund"、"finance:export"
    """
    async def _check(admin: CurrentAdmin) -> None:
        # 聚合该管理员所有角色的权限码集合
        owned_permissions: set[str] = set()
        for role in admin.roles:
            for perm in role.permissions:
                owned_permissions.add(perm.code)

        if permission_code not in owned_permissions:
            from app.domains.admin.constants import AdminError
            raise AppException(
                AdminError.PERMISSION_DENIED,
                message=f"权限不足：缺少 [{permission_code}] 操作权限",
            )

    return Depends(_check)
