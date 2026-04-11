# 技术栈 (STACK)

## 语言与运行时

- **语言**: Python 3.11+ (严格要求 `requires-python = ">=3.11"`)
- **运行时**: CPython (Conda 环境 `fastapi_env`)
- **包管理**: uv (主力) + Conda (环境隔离)
- **构建系统**: hatchling (`[build-system]` in `pyproject.toml`)

## 核心框架

| 框架 | 版本要求 | 用途 |
|---|---|---|
| FastAPI | >=0.121.0 | Web 框架 (ASGI) |
| Uvicorn[standard] | >=0.38.0 | ASGI 服务器 |
| SQLAlchemy[asyncio] | >=2.0.44 | ORM (全异步, Typed 2.0 风格) |
| Pydantic | >=2.12.0 | 数据验证 v2 |
| Pydantic-Settings | >=2.12.0 | 配置管理 (.env 驱动) |
| Alembic | >=1.17.0 | 数据库迁移 |

## 数据库与存储

| 组件 | 版本要求 | 用途 |
|---|---|---|
| PostgreSQL | - | 主数据库 (强制, 不可替换) |
| asyncpg | >=0.30.0 | PG 异步驱动 (运行时) |
| psycopg[binary] | >=3.1.0 | PG 同步驱动 (Alembic 迁移) |
| Redis | >=5.0.0 | 异步客户端 (Refresh Token 存储) |

## 安全与认证

| 库 | 版本要求 | 用途 |
|---|---|---|
| pwdlib[argon2] | >=0.2.0 | 密码哈希 (Argon2id) |
| PyJWT[crypto] | >=2.8.0 | JWT 签发与验签 |
| python-multipart | >=0.0.12 | Form data 支持 |

## 工具链

| 库 | 版本要求 | 用途 |
|---|---|---|
| orjson | >=3.10.0 | 高性能 JSON 序列化 (替代 stdlib json) |
| uuid6 | >=2024.1.12 | UUID v7 生成 (时间有序主键) |
| loguru | >=0.7.2 | 集中式日志 (替代 stdlib logging) |
| email-validator | >=2.1.0 | Pydantic EmailStr 校验 |

## 开发工具

| 工具 | 版本要求 | 用途 |
|---|---|---|
| ruff | >=0.6.0 | 代码格式化与 Lint (含 ASYNC 检查) |
| mypy | >=1.10.0 | 静态类型检查 (含 Pydantic/SQLAlchemy 插件) |
| pytest | >=8.2.0 | 测试框架 |
| pytest-asyncio | >=0.23.0 | 异步测试插件 |
| httpx | >=0.27.0 | 异步 HTTP 测试客户端 |
| pre-commit | >=3.7.0 | Git Hooks |

## 配置管理

- **配置来源**: `.env` 文件 (通过 `pydantic-settings` 加载)
- **配置单例**: `app/core/config.py` → `settings = Settings()`
- **环境分层**: `local` / `dev` / `prod` (由 `ENVIRONMENT` 变量控制)
- **模板文件**: `.env.example` (103 行, 包含完整的配置契约)

### 关键配置项

- `SECRET_KEY`: JWT 签名密钥 (生产环境强制 >=32 字符)
- `SQLALCHEMY_DATABASE_URI`: 可选完整 DSN 覆盖, 否则从 `POSTGRES_*` 字段自动组装
- `REDIS_URL`: Redis 连接串 (默认 `redis://localhost:6379/0`)
- `LOG_*`: Loguru 日志配置族 (级别/格式/轮转/保留)
- `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS`: JWT 有效期

## Ruff 配置亮点

```toml
target-version = "py311"
line-length = 88
select = ["E", "W", "F", "I", "B", "C4", "UP", "T20", "ASYNC", "BLE"]
```

- 启用 `T20` (禁止 print)
- 启用 `ASYNC` (异步代码检查)
- 启用 `BLE` (禁止 `except Exception`)

## Mypy 配置亮点

- `disallow_untyped_defs = true` (强制函数类型注解)
- 使用 `pydantic.mypy` + `sqlalchemy.ext.mypy.plugin` 插件
- 对 `uuid6.*` 豁免导入检查
