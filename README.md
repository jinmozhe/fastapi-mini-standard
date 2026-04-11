# FastAPI V3.0 Standard Project

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.121%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-316192?logo=postgresql)](https://www.postgresql.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-red)](https://www.sqlalchemy.org/)
[![Pydantic](https://img.shields.io/badge/Pydantic-V2-E92063)](https://docs.pydantic.dev/)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE)
[![Ruff](https://img.shields.io/badge/Code%20Style-Ruff-black)](https://github.com/astral-sh/ruff)

**工程规范构建的企业级 FastAPI 后端脚手架。**
严格遵循全链路异步、领域驱动设计 (DDD) 与类型安全标准。

</div>

---

## 📖 目录

- [核心架构特性](#-核心架构特性)
- [技术栈](#-技术栈)
- [项目结构](#-项目结构)
- [已实现的业务功能](#-已实现的业务功能)
- [快速开始](#-快速开始)
- [开发工作流](#-开发工作流)
- [API 响应契约](#-api-响应契约)
- [异常处理体系](#-异常处理体系)
- [安全设计](#-安全设计)
- [部署与运维](#-部署与运维)

---

## 📘 核心架构特性

本项目不仅仅是一个模板，它是一套**工程规范的参考实现**。

```
                  ┌─────────────────────────────────────────────┐
  HTTP Request ──▶│  Router (协议解析/响应封装)                    │
                  └───────────────┬─────────────────────────────┘
                                  ▼
                  ┌─────────────────────────────────────────────┐
                  │  Service (业务逻辑/事务控制/规则校验)           │
                  └───────────────┬─────────────────────────────┘
                                  ▼
                  ┌─────────────────────────────────────────────┐
                  │  Repository (数据持久化/查询)                  │
                  └───────────────┬─────────────────────────────┘
                                  ▼
                  ┌─────────────────────────────────────────────┐
                  │  ORM Models (SQLAlchemy 2.0 Typed)           │
                  └─────────────────────────────────────────────┘
```

| 原则 | 实现 |
|------|------|
| **⚡ Async First** | 全链路异步 (`async`/`await`)，数据库驱动 `asyncpg`，拒绝阻塞 I/O |
| **🛡️ Typed ORM** | SQLAlchemy 2.0 (`Mapped` + `DeclarativeBase`)，强制类型注解 |
| **🏗️ Domain-Oriented** | 领域驱动分层：Router → Service → Repository，`import-linter` 强制约束 |
| **🆔 UUID v7** | 数据库主键与 Request ID 全栈统一 UUID v7 (时间有序 + 随机性) |
| **📦 Unified Response** | 统一响应信封 (`ResponseModel`)，业务错误使用语义化字符串业务码 |
| **🔒 Security** | Argon2id 密码哈希 (`pwdlib`)、JWT 认证 (`PyJWT`)、PII 数据脱敏 |
| **📝 Structured Logging** | Loguru 结构化日志，全链路 `request_id` 追踪，接管 Uvicorn 日志 |

---

## 🔧 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| Web 框架 | FastAPI ≥0.121 + Uvicorn | ASGI 异步服务器，默认 ORJSONResponse |
| ORM | SQLAlchemy 2.0 (Async) | 强类型 `Mapped` + `DeclarativeBase` |
| 数据库 | PostgreSQL + asyncpg | 异步驱动，连接池调优 |
| 数据库迁移 | Alembic + psycopg3 | 同步迁移驱动，避免 EventLoop 问题 |
| 数据验证 | Pydantic V2 | `ConfigDict` + `field_validator` |
| 密码哈希 | pwdlib (Argon2id) | 抗 GPU 破解，异步封装 |
| JWT | PyJWT | 无状态 Access Token 签发与验签 |
| 缓存防刷 | Redis (Async) | Refresh Token 族谱存储 + 滑动窗口高并发限流拦截 |
| 网络请求 | httpx | 替代庞大云厂商 SDK，执行极简无阻断的外部网关校验 |
| 日志 | Loguru | 结构化 JSON 日志，按小时轮转 |
| JSON 序列化 | orjson | 高性能，替代标准库 json |
| UUID | uuid6 | UUID v7 生成 (时间有序) |
| 代码规范 | Ruff + Mypy | Lint/Format + 静态类型检查 |
| 架构约束 | import-linter | 层级依赖 + 领域独立性强制检查 |
| 容器化 | Docker + Docker Compose | 一键部署 App + DB |

---

## 📂 项目结构

```text
.
├── app/                              # 核心应用代码
│   ├── main.py                       # 应用入口：工厂函数 + Lifespan 管理
│   ├── api_router.py                 # 根路由聚合 (auth + users)
│   ├── api/                          # 全局依赖层
│   │   └── deps.py                   #   DB Session / JWT 鉴权 / 权限控制
│   ├── core/                         # 核心基础设施
│   │   ├── config.py                 #   全局配置 (pydantic-settings, .env)
│   │   ├── error_code.py             #   错误码枚举基类 + 系统级错误
│   │   ├── exceptions.py             #   业务异常类 + 全局异常处理器
│   │   ├── logging.py                #   Loguru 日志 (接管 Uvicorn)
│   │   ├── middleware.py             #   中间件 (CORS / RequestID / AccessLog)
│   │   ├── redis.py                  #   Redis 异步客户端
│   │   ├── response.py              #   统一响应信封 (ResponseModel)
│   │   └── security.py              #   密码哈希 (Argon2id) + JWT (PyJWT)
│   ├── db/                           # 数据库层
│   │   ├── session.py                #   AsyncEngine + AsyncSession 工厂
│   │   ├── models/                   #   ORM 模型
│   │   │   ├── base.py               #     基类 (UUIDModel / Mixin 组件)
│   │   │   ├── user.py               #     用户核心账号
│   │   │   ├── user_profile.py       #     用户档案 (PII 加密存储)
│   │   │   └── user_social.py        #     三方登录绑定
│   │   └── repositories/
│   │       └── base.py               #   泛型 CRUD Repository 基类
│   ├── domains/                      # 业务领域 (Bounded Contexts)
│   │   ├── auth/                     #   🔐 认证领域 (登录/注册/Token)
│   │   │   ├── router.py / service.py / schemas.py / constants.py
│   │   ├── users/                    #   👤 用户领域 (查询/更新/注销)
│   │   │   ├── router.py / service.py / repository.py / schemas.py
│   │   │   ├── dependencies.py       #     DI 依赖链组装
│   │   │   └── constants.py          #     错误码 + 成功文案
│   │   └── orders/                   #   📦 订单领域 (待实现)
│   ├── services/                     # 跨领域业务编排 (Use Cases)
│   └── utils/
│       └── masking.py                # PII 数据脱敏工具
├── tests/                            # Pytest 测试套件
│   ├── conftest.py                   #   全局 Fixtures (异步 DB + HTTP Client)
│   ├── unit/                         #   单元测试
│   └── integration/                  #   集成测试
├── alembic/                          # 数据库迁移
│   └── env.py                        #   同步迁移配置 (psycopg3, Windows 兼容)
├── scripts/                          # 运维脚本 (init_db / seed_data)
├── docs/                             # 项目文档
├── pyproject.toml                    # 项目配置 (依赖 + 工具链)
├── requirements.txt                  # 依赖清单 (与 pyproject.toml 对齐)
├── .env.example                      # 环境变量模板
├── .importlinter                     # 架构约束规则
├── Dockerfile                        # Docker 构建
└── docker-compose.yml                # Docker Compose 编排
```

---

## 🏢 已实现的业务功能

### 认证领域 (Auth)

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 用户注册 | `POST` | `/api/v1/auth/register` | 手机号+密码注册 → 自动登录 → 返回双 Token |
| 用户登录 | `POST` | `/api/v1/auth/login` | 手机号+密码 → JWT Access Token + Refresh Token |
| 刷新令牌 | `POST` | `/api/v1/auth/refresh` | Token Rotation：旧 Token RENAME 重命钓鱼，签发新对 |
| 用户登出 | `POST` | `/api/v1/auth/logout` | 顺藤摸瓜拔除关联 Session 族谱的所有合规 Token |

- **Refresh Token 洗劫防御**: Redis 原生 `RENAME` 拦截，识别异常窃用并发，顺带通过 SessionID 追剿当前合规 Token（“诛九族/连坐机制”）。
- **暴力拆解防御**: 高危认证路由强绑定 `Depends(RateLimiter)`，拦截异常算力耗尽。
- **人机安全掩码**: 基于 `httpx` 构建独立轻量验证码护盾 `CAPTCHA_ENABLE` 热插拔逃生舱策略，登录失败统一返回防枚举状态。

### 用户领域 (Users)

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 查询个人信息 | `GET` | `/api/v1/users/me` | 需鉴权，直接返回当前用户 |
| 更新个人资料 | `PATCH` | `/api/v1/users/me` | 需鉴权，支持改密码/手机号/邮箱，含唯一性校验 |
| 注销账户 | `DELETE` | `/api/v1/users/me` | 需鉴权，软删除 (is_deleted + deleted_at) |

### 数据模型

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| `users` | 核心账号 | phone_number, email, username, hashed_password, is_active, is_superuser |
| `user_profiles` | 用户档案 (1:1) | real_name_enc (密文), identity_card_enc (密文), OCR 数据 |
| `user_socials` | 三方绑定 (N:1) | platform, openid, unionid, extra_data (JSONB) |

> **注意**: 采用 **No-Relationship 模式** — 不定义 ORM relationship，关联通过外键约束 + 显式 JOIN 实现。所有模型继承自 `UUIDModel` (UUID v7 主键 + UTC 时间戳)。

---

## 🚀 快速开始

### 1. 环境准备

确保本地已安装 **Python 3.11+**、**PostgreSQL** 和 **Redis**。

```bash
# 克隆项目
git clone https://github.com/jinmozhe/fastapi_standard.git
cd fastapi_standard_project

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 安装 Pre-commit 钩子 (可选)
pre-commit install
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，确保以下关键配置正确：

| 变量 | 说明 | 示例 |
|------|------|------|
| `SECRET_KEY` | JWT 签名密钥 (≥32 字符) | `your-super-secret-random-key-here` |
| `POSTGRES_SERVER` | PostgreSQL 地址 | `localhost` |
| `POSTGRES_PORT` | PostgreSQL 端口 | `5432` |
| `POSTGRES_USER` | 数据库用户名 | `postgres` |
| `POSTGRES_PASSWORD` | 数据库密码 | `password` |
| `POSTGRES_DB` | 数据库名 | `fastapi_db` |
| `REDIS_URL` | Redis 连接地址 | `redis://localhost:6379/0` |

### 3. 数据库初始化

```bash
# 应用数据库迁移
alembic upgrade head

# (可选) 填充种子数据
python scripts/seed_data.py
```

### 4. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> **注意**: 文档路径已做混淆处理，使用 `/pinjie` 前缀。

访问文档：
- **Swagger UI**: [http://localhost:8000/pinjie/docs](http://localhost:8000/pinjie/docs)
- **ReDoc**: [http://localhost:8000/pinjie/redoc](http://localhost:8000/pinjie/redoc)
- **健康检查**: [http://localhost:8000/pinjie/health](http://localhost:8000/pinjie/health)

---

## 🛠️ 开发工作流

### 数据库迁移 (Alembic)

项目使用 **psycopg3 (同步)** 驱动执行迁移，与运行时的 asyncpg 分离，完美兼容 Windows。

```bash
# 1. 修改 app/db/models 下的模型后，生成迁移脚本
alembic revision --autogenerate -m "描述你的变更"

# 2. 检查生成的 alembic/versions/xxxx.py 文件

# 3. 应用变更到数据库
alembic upgrade head
```

### 运行测试

```bash
# 运行所有测试 (自动使用 fastapi_test 独立测试库)
pytest

# 运行特定测试并显示详细信息
pytest tests/unit/test_users.py -vv
```

> 测试基础设施使用 `pytest-asyncio` (Session 级 Event Loop)。测试配置会自动将 DB 指向 `fastapi_test` 数据库，并在测试前后重置 Schema。

### 代码规范检查

```bash
# Ruff Lint + Format
ruff check .
ruff format .

# Mypy 静态类型检查
mypy app/

# 架构约束检查 (领域独立性 / 层级依赖)
lint-imports
```

---

## 📦 API 响应契约

所有接口统一返回 `ResponseModel` 信封格式：

### 成功响应

```json
{
  "code": "success",
  "message": "Success",
  "data": {
    "id": "018e65c9-3a5b-7b22-8c4d-9e5f1a2b3c4d",
    "phone_number": "+8613800000000",
    "email": "user@example.com"
  },
  "request_id": "018e65c9-4b7a-7c33-9d5e-0f6a2b3c4d5e",
  "timestamp": "2026-04-03T10:00:00Z"
}
```

### 业务错误响应

```json
{
  "code": "user.phone_exist",
  "message": "该手机号已被其他用户注册",
  "data": null,
  "request_id": "018e65c9-4b7a-7c33-9d5e-0f6a2b3c4d5e",
  "timestamp": "2026-04-03T10:00:00Z"
}
```

> **错误码格式**: `{domain}.{reason}` (如 `auth.invalid_credentials`, `user.not_found`, `system.internal_error`)

---

## 🚨 异常处理体系

项目实现了**四级异常捕获**，确保任何错误都返回统一响应格式：

| 异常类型 | 处理器 | HTTP 状态码 | 场景 |
|---------|--------|------------|------|
| `AppException` | `app_exception_handler` | 4xx (由错误码定义) | 业务逻辑异常 |
| `RequestValidationError` | `validation_exception_handler` | 400 | Pydantic 参数校验失败 |
| `StarletteHTTPException` | `http_exception_handler` | 404/405 等 | 路由未匹配等框架异常 |
| `Exception` | `general_exception_handler` | 500 | 未捕获的系统异常 (最后防线) |

自定义业务异常用法：

```python
from app.core.exceptions import AppException
from app.domains.auth.constants import AuthError

# Service 层抛出业务异常
raise AppException(AuthError.INVALID_CREDENTIALS)
raise AppException(AuthError.PHONE_EXIST, message="自定义文案覆盖默认值")
```

---

## 🔒 安全设计

| 特性 | 实现细节 |
|------|---------|
| 密码存储 | Argon2id 哈希 (`pwdlib`)，强烈防御 GPU 破解但极其占用 CPU，必须配合频控 |
| 防暴撞库 | 高危层强挂 `Depends(RateLimiter)`，启用极高性能的原生 Redis 滑动窗口频控 |
| 人机识别 | 原生 `httpx` 对接云验证协议，附带旁路的 `CAPTCHA_ENABLE` 热安全逃生舱 |
| 身份认证 | JWT Access Token (HS256, 30 分钟有效) |
| 令牌防盗用 | 族谱级树型追踪与 `RENAME` 钓鱼，截获黑客并发窃用后立刻启动“诛连”销毁 |
| 权限控制 | `CurrentUser` (已登录) → `SuperUser` (超管) 依赖注入链 |
| 防枚举攻击 | 登录失败统一返回 `auth.invalid_credentials`，不区分用户名/密码错误 |
| PII 脱敏 | 日志中自动过滤 password/token/card_number 等敏感字段 |
| 数据加密 | 用户档案表敏感字段 (real_name, identity_card) 加密存储 |
| 文档混淆 | Swagger/ReDoc/OpenAPI 路径使用 `/pinjie` 混淆前缀 |

---

## 🐳 部署与运维

### Docker Compose (推荐)

```bash
# 构建并后台启动全栈环境 (App + DB + Redis)
docker-compose up -d --build

# 查看实时日志
docker-compose logs -f app
```

### 手动部署

```bash
# 生产环境启动 (多 Worker)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 关键配置

| 环境 | `ENVIRONMENT` | `DEBUG` | `LOG_JSON_FORMAT` | `LOG_DIAGNOSE` |
|------|--------------|---------|-------------------|----------------|
| 本地开发 | `local` | `true` | `false` | `true` |
| 测试环境 | `dev` | `false` | `true` | `true` |
| 生产环境 | `prod` | `false` | `true` | `false` |

> ⚠️ 生产环境强制要求 `SECRET_KEY` 长度 ≥ 32 字符，所有 `POSTGRES_*` 环境变量不可为空。

---

## 📄 License

MIT © [jinmozhe](https://github.com/jinmozhe)
