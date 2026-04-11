"""
File: app/db/session.py
Description: 数据库会话管理 (Async SQLAlchemy)

本模块负责：
1. 创建全局唯一的 AsyncEngine (基于 postgresql+asyncpg)
2. 配置连接池参数 (pool_pre_ping, pool_size 等)，从 Settings 读取
3. 创建 AsyncSession 工厂 (AsyncSessionLocal)
4. 集成 orjson 用于高性能 JSON 字段序列化
5. 提供引擎关闭函数用于优雅退出

Author: jinmozhe
Created: 2025-11-24
"""

from typing import Any

import orjson
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _orjson_serializer(obj: Any) -> str:
    """
    使用 orjson 替代标准库 json.dumps。
    orjson 返回 bytes，SQLAlchemy 需要 str，因此需 decode。
    """
    return orjson.dumps(obj).decode("utf-8")


def _orjson_deserializer(obj: str | bytes) -> Any:
    """
    使用 orjson 替代标准库 json.loads。
    """
    return orjson.loads(obj)


# 1. 创建异步引擎
# echo=True 会在控制台打印生成的 SQL 语句，建议仅在 DEBUG 模式开启
engine: AsyncEngine = create_async_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    echo=settings.DEBUG,
    # 连接池配置 (统一从 config.py 读取，方便生产环境调优)
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    # 高性能 JSON 序列化配置
    json_serializer=_orjson_serializer,
    json_deserializer=_orjson_deserializer,
    connect_args={"ssl": False},  # 根据需要配置 SSL 连接参数
)

# 2. 创建异步会话工厂
# expire_on_commit=False 是 AsyncSession 的强制要求
# 避免在 commit 后访问属性时触发隐式 IO (Async 模式下不支持)
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def close_engine() -> None:
    """
    关闭数据库引擎，释放连接池资源。
    应在应用 shutdown 事件中调用。
    """
    await engine.dispose()
