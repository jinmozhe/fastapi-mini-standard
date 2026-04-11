# 目录结构 (STRUCTURE)

## 项目根目录

```
fastapi-mini-standard/
├── .env                          # 环境变量 (被 .gitignore 忽略)
├── .env.example                  # 环境变量模板 (103 行, 配置契约)
├── .gitignore                    # Git 忽略规则 (100 行)
├── .importlinter                 # 导入规则强制约束 (67 行)
├── pyproject.toml                # 项目依赖 + 工具配置 (116 行)
├── requirements.txt              # 锁定依赖清单 (45 行)
├── README.md                     # 项目说明文档 (16KB)
├── 可运行项目模板使用说明.md       # 中文使用说明
├── Dockerfile                    # Docker 构建 (空)
├── docker-compose.yml            # Docker 编排 (空)
├── alembic.ini                   # Alembic 迁移配置 (48 行)
├── alembic/                      # 数据库迁移
│   └── env.py                    # 迁移环境 (121 行, Psycopg3 同步方式)
└── app/                          # 应用主目录
    ├── __init__.py               # 包标记
    ├── main.py                   # 应用入口 + 工厂函数 (130 行)
    ├── api_router.py             # 路由聚合层 (44 行)
    ├── api/                      # 全局 API 层
    │   ├── __init__.py
    │   └── deps.py               # 全局依赖注入 (133 行)
    ├── core/                     # 横切关注点
    │   ├── config.py             # 配置管理 (165 行)
    │   ├── error_code.py         # 错误码基类 + 系统错误码 (75 行)
    │   ├── exceptions.py         # 业务异常 + 全局异常处理器 (218 行)
    │   ├── logging.py            # Loguru 日志配置 (136 行)
    │   ├── middleware.py         # 中间件 (123 行)
    │   ├── redis.py              # Redis 客户端管理 (59 行)
    │   ├── response.py           # 统一响应信封 (84 行)
    │   └── security.py           # 密码 + JWT 工具 (129 行)
    ├── db/                       # 数据访问层
    │   ├── session.py            # AsyncEngine + SessionFactory (78 行)
    │   ├── models/               # ORM 模型
    │   │   ├── __init__.py       # 模型注册表 (49 行)
    │   │   ├── base.py           # 基类 + Mixin (175 行)
    │   │   └── user.py           # 用户模型 (105 行)
    │   └── repositories/         # 仓储层
    │       ├── __init__.py
    │       └── base.py           # 通用 CRUD Repository (168 行)
    ├── domains/                  # 业务领域
    │   ├── __init__.py
    │   ├── auth/                 # 认证领域
    │   │   ├── constants.py      # 错误码 + 成功提示 (79 行)
    │   │   ├── router.py         # 路由 (161 行)
    │   │   ├── schemas.py        # 数据模型 (85 行)
    │   │   └── service.py        # 服务层 (213 行)
    │   └── users/                # 用户领域
    │       ├── __init__.py
    │       ├── constants.py      # 错误码 + 成功提示 (38 行)
    │       ├── dependencies.py   # 依赖注入链 (57 行)
    │       ├── repository.py     # 用户仓储 (84 行)
    │       ├── router.py         # 路由 (109 行)
    │       ├── schemas.py        # 数据模型 (119 行)
    │       └── service.py        # 服务层 (118 行)
    ├── services/                 # 跨域服务层 (当前为空)
    │   └── __init__.py
    ├── utils/                    # 工具集
    │   ├── __init__.py
    │   └── masking.py            # PII 数据脱敏 (128 行)
    └── static/                   # 静态资源 (ReDoc JS/Favicon)
```

## 关键文件索引

### 配置与启动

| 文件 | 职责 |
|---|---|
| `app/main.py` | 应用工厂, 生命周期, 组件注册 |
| `app/core/config.py` | 全局配置单例 (`settings`) |
| `app/api_router.py` | 路由聚合 (auth, users, admin) |
| `.env.example` | 配置契约模板 |

### 基础设施

| 文件 | 职责 |
|---|---|
| `app/db/session.py` | 数据库引擎 + 会话工厂 |
| `app/core/redis.py` | Redis 客户端单例 |
| `app/core/middleware.py` | Request ID + Access Log + CORS |
| `app/core/logging.py` | Loguru 配置 (拦截 stdlib) |
| `app/core/security.py` | 密码哈希 (Argon2) + JWT 签发 |

### 核心抽象

| 文件 | 职责 |
|---|---|
| `app/db/models/base.py` | ORM 基类 + Mixin (UUID, Timestamp, SoftDelete) |
| `app/db/repositories/base.py` | 通用 CRUD Repository (泛型) |
| `app/core/response.py` | 统一响应信封 `ResponseModel[T]` |
| `app/core/error_code.py` | 错误码枚举基类 `BaseErrorCode` |
| `app/core/exceptions.py` | 业务异常 `AppException` + 全局处理器 |

## 命名约定

### 文件命名

| 类型 | 约定 | 示例 |
|---|---|---|
| 领域模块文件 | `router.py` / `service.py` / `schemas.py` / `repository.py` / `constants.py` / `dependencies.py` | 固定文件名, 跨领域一致 |
| ORM 模型 | `snake_case.py` | `user.py`, `base.py` |
| 配置/工具 | `snake_case.py` | `config.py`, `masking.py` |

### 类命名

| 类型 | 约定 | 示例 |
|---|---|---|
| ORM 模型 | `PascalCase` (单数) | `User`, `UserProfile` |
| Repository | `{Model}Repository` | `UserRepository` |
| Service | `{Domain}Service` | `AuthService`, `UserService` |
| Schema | `{Model}{Action}` | `UserRead`, `UserUpdate`, `LoginRequest` |
| 错误码 | `{Domain}Error(BaseErrorCode)` | `AuthError`, `UserError` |
| 提示语 | `{Domain}Msg` | `AuthMsg`, `UserMsg` |
| 依赖别名 | `{Type}Dep` | `AuthServiceDep`, `UserServiceDep` |

### 表命名

- ORM 类名自动转 `snake_case` (via `resolve_table_name`)
- `User` 类手动覆盖为 `users` (复数)
- 约束命名约定: `ix_`, `uq_`, `ck_`, `fk_`, `pk_` 前缀

### 领域模块标准结构

```
app/domains/{domain_name}/
├── __init__.py       # (可选)
├── constants.py      # 错误码 + 成功消息
├── dependencies.py   # 依赖注入链 (Repo → Service → Dep)
├── repository.py     # 数据访问
├── router.py         # HTTP 路由
├── schemas.py        # Pydantic 输入/输出
└── service.py        # 业务逻辑
```
