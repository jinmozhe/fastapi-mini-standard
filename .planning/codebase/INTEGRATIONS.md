# INTEGRATIONS.md — 外部集成

## 1. PostgreSQL（核心数据库）
- **连接方式**: 全异步（`asyncpg` 驱动 + `create_async_engine`）
- **配置来源**: `app/core/config.py` → `.env` 文件中的 `POSTGRES_*` 系列字段
- **连接池**: SQLAlchemy 内置池（`pool_pre_ping=True`, 配置化 `pool_size/max_overflow`）
- **JSON 优化**: Engine 层集成 `orjson` 序列化/反序列化
- **会话工厂**: `app/db/session.py` → `AsyncSessionLocal`（`expire_on_commit=False`）
- **Alembic 迁移**: 使用独立的同步驱动 `psycopg`（`alembic/env.py`），避免 Windows EventLoop 问题

## 2. Redis（缓存与 Token 存储）
- **客户端**: `redis.asyncio.Redis`（全局单例，`app/core/redis.py`）
- **连接配置**: `.env` → `REDIS_URL=redis://localhost:6379/0`
- **用途**:
  - Refresh Token 存储（Key: `refresh_token:{token}` → Value: `user_id`，TTL: 7 天）
  - 未来可扩展：缓存、分布式锁、限流
- **生命周期**: `lifespan` 中 `close_redis()` 优雅关闭

## 3. 本地静态文件
- **挂载路径**: `/static` → `app/static/`
- **用途**: ReDoc 文档资源本地化（`redoc.standalone.js`、`favicon.png`），禁用 Google Fonts

## 4. 外部 API
- **当前**: 无外部 HTTP API 集成
- **预留**: `app/services/` 目录已存在但为空，为未来接入第三方服务预留

## 5. CORS 跨域
- **配置**: `BACKEND_CORS_ORIGINS` (JSON 列表格式，Pydantic 自动解析)
- **默认**: `["http://localhost:8000", "http://localhost:3000"]`
