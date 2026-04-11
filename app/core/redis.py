"""
File: app/core/redis.py
Description: Redis 客户端管理 (Async)

本模块负责：
1. 创建全局 Redis 连接池 (基于 redis-py 的 asyncio 扩展)
2. 提供依赖注入所需的 Redis 客户端生成器
3. 管理连接生命周期 (初始化与关闭)

注意：
使用 decode_responses=True，确保从 Redis 读取的数据自动解码为 str，
避免在业务逻辑中处理 bytes 类型。

Author: jinmozhe
Created: 2025-12-05
"""

from collections.abc import AsyncGenerator

from redis.asyncio import Redis, from_url

from app.core.config import settings

# ------------------------------------------------------------------------------
# 全局 Redis 客户端实例 (Singleton)
# ------------------------------------------------------------------------------
# redis-py 内部维护了连接池 (ConnectionPool)，因此创建一个全局实例是最佳实践。
# 所有的 CRUD 操作都会自动从池中获取连接并在使用后归还。
redis_client: Redis = from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)


async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    获取 Redis 客户端依赖。

    用法:
    @router.get("/")
    async def endpoint(redis: Annotated[Redis, Depends(get_redis)]):
        val = await redis.get("key")

    虽然 redis_client 是全局单例，但将其封装为依赖注入 (Generator) 有以下好处：
    1. 统一接口：Router 不需要导入全局变量，保持松耦合。
    2. 测试友好：在单元测试中可以轻松 override 这个依赖，注入 MockRedis。
    """
    yield redis_client


async def close_redis() -> None:
    """
    关闭 Redis 连接池。
    应在 FastAPI 应用的 lifespan shutdown 事件中调用，
    确保应用退出时释放所有 Redis 连接资源。
    """
    await redis_client.close()
