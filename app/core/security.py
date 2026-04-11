"""
File: app/core/security.py
Description: 安全工具模块 (Argon2id + JWT)

本模块负责：
1. 密码加密 (Hash): 使用 Argon2id 算法 (抗 GPU 破解)
2. 密码验证 (Verify): 校验明文与哈希
3. JWT 签发: 生成无状态的 Access Token
4. 异步封装: 针对 CPU 密集型操作提供 async 支持

Author: jinmozhe
Created: 2025-12-05
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash
from starlette.concurrency import run_in_threadpool

from app.core.config import settings

# 初始化密码哈希处理器
# pwdlib[argon2] 默认使用 argon2 算法
password_hash = PasswordHash.recommended()

# ------------------------------------------------------------------------------
# 1. 密码处理 (Password Hashing)
# ------------------------------------------------------------------------------


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码与哈希值是否匹配。

    Args:
        plain_password: 用户输入的明文密码
        hashed_password: 数据库存的哈希值 (Argon2 格式)

    Returns:
        bool: 匹配返回 True，否则 False
    """
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    生成密码哈希值 (Argon2id)。

    Args:
        password: 明文密码

    Returns:
        str: 加密后的哈希字符串
    """
    return password_hash.hash(password)


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """
    异步验证密码（在线程池中执行，避免阻塞事件循环）。

    Args:
        plain_password: 用户输入的明文密码
        hashed_password: 数据库存的哈希值

    Returns:
        bool: 匹配返回 True，否则 False
    """
    return await run_in_threadpool(verify_password, plain_password, hashed_password)


async def get_password_hash_async(password: str) -> str:
    """
    异步生成密码哈希（在线程池中执行，避免阻塞事件循环）。

    Args:
        password: 明文密码

    Returns:
        str: 加密后的哈希字符串
    """
    return await run_in_threadpool(get_password_hash, password)


# ------------------------------------------------------------------------------
# 2. JWT 处理 (JSON Web Token)
# ------------------------------------------------------------------------------


def create_access_token(
    subject: str | Any,
    expires_delta: timedelta | None = None,
    extra_claims: dict | None = None,
) -> str:
    """
    生成 JWT Access Token (短效, 无状态)。

    Args:
        subject: 主体标识 (通常为 user_id 或 admin_id)
        expires_delta: 自定义过期时间差 (可选，默认为配置中的 ACCESS_TOKEN_EXPIRE_MINUTES)
        extra_claims: 额外注入的 JWT 载荷字段，如 {"aud": "backend"} 用于区分 B/C 端 Token

    Returns:
        str: 编码后的 JWT 字符串

    Raises:
        ValueError: 如果系统配置中缺失 SECRET_KEY
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    # 防御性检查，同时解决 Pylance 报错
    # 静态检查器现在知道 secret_key 必定是 str 类型
    secret_key = settings.SECRET_KEY
    if secret_key is None:
        raise ValueError("SECRET_KEY configuration is missing.")

    # 构造基础 Payload
    # sub: Subject (用户/管理员ID)
    # exp: Expiration Time (过期时间戳)
    # type: Token 类型 (标识为 access token)
    to_encode: dict[str, Any] = {"exp": expire, "sub": str(subject), "type": "access"}

    # 注入扩展字段（如 B 端专属的 aud='backend' 标识）
    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=settings.ALGORITHM)
    return encoded_jwt
