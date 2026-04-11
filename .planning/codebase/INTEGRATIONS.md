# 外部集成 (INTEGRATIONS)

## 1. PostgreSQL 数据库

**连接方式**: 双驱动策略

| 场景 | 驱动 | DSN 协议前缀 |
|---|---|---|
| 运行时 (FastAPI) | `asyncpg` | `postgresql+asyncpg://` |
| 迁移 (Alembic) | `psycopg` (v3) | `postgresql+psycopg://` |

**连接池配置** (来自 `app/core/config.py`):

```python
pool_pre_ping=True    # 自动健康检查
pool_size=20          # 基准大小
max_overflow=10       # 额外连接数
pool_timeout=30       # 获取超时 (秒)
pool_recycle=1800     # 回收时间 (秒)
```

**引擎创建**: `app/db/session.py`
- 集成 `orjson` 作为 JSON 序列化器/反序列化器
- `expire_on_commit=False` (异步必须)
- `autoflush=False` (手动控制刷新)
- SSL 默认关闭 (`connect_args={"ssl": False}`)

**迁移**: `alembic/env.py`
- 同步模式运行, 使用 `psycopg` 驱动
- 对密码中的特殊字符做 `quote_plus` 编码
- 支持离线模式 (生成 SQL 脚本)
- `compare_type=True` + `compare_server_default=True`

## 2. Redis

**客户端**: `redis.asyncio` (redis-py 异步接口)

**连接**: `app/core/redis.py`
- 全局单例 `redis_client` 通过 `from_url()` 创建
- `decode_responses=True` (自动解码为 `str`)
- 提供依赖注入 `get_redis()` → `AsyncGenerator[Redis, None]`
- 生命周期通过 `close_redis()` 在 lifespan shutdown 中关闭

**用途**:
- Refresh Token 存储 (Key: `refresh_token:{token}` → Value: `user_id`)
- Token 有效期: `REFRESH_TOKEN_EXPIRE_DAYS` 天 (默认 7 天)
- 用于 Token Rotation 策略 (刷新时销毁旧 token)

**环境变量**: `REDIS_URL` (默认 `redis://localhost:6379/0`)

## 3. JWT 认证

**库**: PyJWT[crypto] (非 python-jose)

**签发**: `app/core/security.py` → `create_access_token()`
- 算法: `HS256` (可配置)
- Payload: `{sub: user_id, exp: timestamp, type: "access"}`
- 密钥: `settings.SECRET_KEY`

**验签**: `app/api/deps.py` → `get_current_user()`
- 从 `Authorization: Bearer <token>` 手动解析
- 不使用 OAuth2PasswordBearer (手动实现 Header 提取)
- 验签后额外查库校验: 用户存在、未软删除、已激活

## 4. 密码安全

**库**: pwdlib[argon2]

**实现**: `app/core/security.py`
- `get_password_hash()` / `verify_password()` (同步)
- `get_password_hash_async()` / `verify_password_async()` (通过 `run_in_threadpool` 封装)
- 使用 `PasswordHash.recommended()` 默认配置

## 5. 日志 (Loguru)

**配置**: `app/core/logging.py` → `setup_logging()`
- 拦截 Python `stdlib logging` → 转发到 Loguru
- 控制台: 彩色格式 (dev) / JSON 格式 (prod, 可配)
- 文件: 按小时轮转, 7 天保留, zip 压缩 (可配)
- 上下文绑定: `request_id` 自动注入 (通过中间件 `contextualize`)

## 6. 容器化 (待实现)

- `Dockerfile`: 空文件 (尚未实现)
- `docker-compose.yml`: 空文件 (尚未实现)
- 预期用于编排 PostgreSQL + Redis + App 容器

## 7. OpenAPI 文档

**配置**: `app/main.py`
- Swagger UI: `/pinjie/docs` (混淆前缀)
- ReDoc: `/pinjie/redoc` (手动路由, 本地 JS/Favicon)
- OpenAPI Schema: `/pinjie/openapi.json`
- ReDoc 禁用 Google Fonts, 使用系统字体
- 静态资源挂载: `app/static/` → `/static`
