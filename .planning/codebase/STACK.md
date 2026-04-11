# STACK.md — 技术栈

## 语言与运行时
- **语言**: Python 3.11+（强制要求 `requires-python = ">=3.11"`）
- **运行时**: CPython
- **包管理**: uv（`uv.lock` 锁定精确版本），基于 `pyproject.toml`（hatchling 构建后端）
- **环境隔离**: Conda（`fastapi_env`）

## 核心框架
| 组件 | 库 | 版本基线 | 用途 |
|---|---|---|---|
| Web 框架 | FastAPI | ≥0.121.0 | 路由、依赖注入、OpenAPI 文档 |
| ASGI 服务器 | Uvicorn[standard] | ≥0.38.0 | 生产级 HTTP 服务 |
| ORM | SQLAlchemy[asyncio] | ≥2.0.44 | 全异步 ORM，Mapped/mapped_column 声明式 |
| 数据验证 | Pydantic | ≥2.12.0 | Schema 校验、响应序列化 |
| 配置管理 | pydantic-settings | ≥2.12.0 | `.env` 文件自动加载 |

## 数据库与驱动
| 组件 | 库 | 用途 |
|---|---|---|
| 数据库 | PostgreSQL | 唯一允许的数据库 |
| 异步驱动 | asyncpg ≥0.30.0 | 运行时高性能连接 |
| 同步驱动 | psycopg[binary] ≥3.1.0 | Alembic 迁移专用 |
| 迁移工具 | Alembic ≥1.17.0 | 数据库版本管理（同步 `env.py`，Windows 兼容） |
| JSON 序列化 | orjson ≥3.10.0 | 替代标准库 json，集成到 SQLAlchemy Engine |

## 认证与安全
| 组件 | 库 | 用途 |
|---|---|---|
| 密码哈希 | pwdlib[argon2] ≥0.2.0 | Argon2id 算法，异步线程池调用 |
| JWT | PyJWT[crypto] ≥2.8.0 | Access Token 签发/验签 |
| UUID | uuid6 ≥2024.1.12 | UUID v7 主键生成（时间有序） |

## 缓存与中间件
| 组件 | 库 | 用途 |
|---|---|---|
| 缓存 | redis ≥5.0.0 | Refresh Token 存储、会话管理 |
| 日志 | loguru ≥0.7.2 | 替代标准库 logging，彩色控制台 + JSON 文件输出 |

## 开发工具链
| 工具 | 版本 | 用途 |
|---|---|---|
| Ruff | ≥0.6.0 | Lint + Format（含 ASYNC 规则） |
| Mypy | ≥1.10.0 | 静态类型检查（含 Pydantic/SQLAlchemy 插件） |
| Pytest | ≥8.2.0 | 测试框架 |
| pytest-asyncio | ≥0.23.0 | 异步测试 |
| httpx | ≥0.27.0 | 测试用 HTTP 客户端 |
| pre-commit | ≥3.7.0 | Git Hooks |

## 配置管理
- 配置入口: `app/core/config.py` → `Settings(BaseSettings)`
- 数据来源: `.env` 文件（`env_file=".env"`, `case_sensitive=True`）
- DSN 构建: 优先 `SQLALCHEMY_DATABASE_URI` 覆盖，否则从 `POSTGRES_*` 分拆字段自动组装
- 连接池: `DB_POOL_SIZE=20`, `DB_MAX_OVERFLOW=10`, `DB_POOL_PRE_PING=True`
