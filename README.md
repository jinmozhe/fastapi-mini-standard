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

基于 FastAPI + Pydantic V2 + SQLAlchemy 2.0 (Async) + Alembic + PostgreSQL 构建的极简且**符合大厂中后台与双轨安全边界标准**的后端骨架项目。适合作为现代 Web/AI 原生应用、复杂电商 B/C 隔离系统的初始脚手架。

> **当前版本进度**：脚手架基建已稳定，正在深度实现电商 C 端全链路业务域 (商品体系、购物车、地址、订单)。

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
│   ├── api_router.py                 # 根路由聚合 (12 个路由域)
│   ├── api/                          # 全局依赖层
│   │   └── deps.py                   #   DB Session / C端 JWT / B端 JWT / OptionalCurrentUser / RBAC 权限工厂
│   ├── core/                         # 核心基础设施
│   │   ├── config.py                 #   全局配置 (pydantic-settings, .env)
│   │   ├── error_code.py             #   错误码枚举基类 + 系统级错误
│   │   ├── exceptions.py             #   业务异常类 + 全局异常处理器
│   │   ├── logging.py                #   Loguru 日志 (接管 Uvicorn)
│   │   ├── middleware.py             #   中间件 (CORS / RequestID / AccessLog / AuditLog)
│   │   ├── audit.py                  #   B端全量操作审计中间件 (AuditLogMiddleware)
│   │   ├── rate_limit.py             #   Redis 滑动窗口限流依赖 (RateLimiter)
│   │   ├── captcha.py                #   验证码云网关旁路校验 (CAPTCHA_ENABLE 热插拔)
│   │   ├── redis.py                  #   Redis 异步客户端
│   │   ├── response.py               #   统一响应信封 (ResponseModel)
│   │   ├── security.py               #   密码哈希 (Argon2id) + JWT (含 aud 双端隔离)
│   │   ├── sms.py                    #   短信验证码 (腾讯云SMS + Redis防刷 + 暴力破解保护)
│   │   ├── validators.py             #   共享校验常量 (手机号/区号正则)
│   │   └── wechat.py                 #   微信工具 (小程序code2session + 开放平台OAuth + AES解密)
│   ├── db/                           # 数据库层
│   │   ├── session.py                #   AsyncEngine + AsyncSession 工厂
│   │   ├── models/                   #   ORM 模型 (集中管理，Alembic 自动发现)
│   │   │   ├── base.py               #     基类 (UUIDModel / SoftDeleteMixin)
│   │   │   ├── user.py               #     C端用户核心账号
│   │   │   ├── user_social.py        #     三方登录绑定
│   │   │   ├── user_level.py         #     会员等级体系
│   │   │   ├── user_wallet.py        #     用户钱包 (余额/积分/流水)
│   │   │   ├── sms_log.py            #     短信发送审计日志
│   │   │   ├── admin.py              #     B端 RBAC 5表
│   │   │   ├── log.py                #     安全审计日志
│   │   │   ├── product.py            #     商品体系 (6表：分类/商品/SKU/规格/等级价/分佣)
│   │   │   ├── media.py              #     媒体素材 (media_assets)
│   │   │   ├── product_view.py       #     商品浏览足迹 (product_views)
│   │   │   ├── cart.py               #     购物车 (cart_items，双轨身份)
│   │   │   └── address.py            #     收货地址 (addresses，含行政编码)
│   │   └── repositories/
│   │       └── base.py               #   泛型 CRUD Repository 基类
│   ├── domains/                      # 业务领域 (Bounded Contexts)
│   │   ├── auth/                     #   C端认证领域 (多渠道登录/注册/Token/社交绑定)
│   │   ├── users/                    #   C端用户领域 (查询/更新/注销)
│   │   ├── user_levels/              #   会员等级领域 (等级规则/升降级/分佣奖励)
│   │   ├── user_wallets/             #   用户钱包领域 (余额签到/积分/流水/B端管控)
│   │   ├── admin/                    #   B端管理员领域 (登录/权限树/RBAC)
│   │   ├── products/                 #   商品领域 (分类树/SPU/SKU/5级价格/3级分佣/足迹)
│   │   ├── media/                    #   媒体素材领域 (图片上传/压缩/LocalStorage)
│   │   ├── carts/                    #   购物车领域 (双轨挂车/游客合并/实时计价)
│   │   └── addresses/                #   收货地址领域 (默认互斥/行政编码/快照预留)
│   └── utils/
│       └── masking.py                # PII 数据脱敏工具
├── tests/                            # Pytest 测试套件
├── alembic/                          # 数据库迁移
│   └── env.py                        #   同步迁移配置 (psycopg3, Windows 兼容)
├── scripts/                          # 运维脚本
│   └── seed_admin.py                 #   超级管理员初始化种子脚本 (幂等)
├── docs/                             # 项目文档
├── pyproject.toml                    # 项目配置 (依赖 + 工具链)
├── .env.example                      # 环境变量模板
├── .importlinter                     # 架构约束规则
├── Dockerfile                        # Docker 构建
└── docker-compose.yml                # Docker Compose 编排
```

---

## 🏢 已实现的业务功能

### C端认证领域 (Auth)

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 用户注册 | `POST` | `/api/v1/auth/register` | 手机号+密码注册，自动登录返回双 Token |
| 用户登录 | `POST` | `/api/v1/auth/login` | 手机号+密码，JWT Access Token + Refresh Token |
| 发送验证码 | `POST` | `/api/v1/auth/sms/send` | 60秒冷却+限流5次/分+审计日志 |
| 短信登录 | `POST` | `/api/v1/auth/sms/login` | 手机号+验证码，不存在自动注册 |
| 小程序登录 | `POST` | `/api/v1/auth/wechat/login` | wx.login()+解密手机号→合流/新建 |
| 微信扫码 | `POST` | `/api/v1/auth/wechat/scan` | 网页端扫码（老用户→Token，新用户→temp_token） |
| 扫码完成注册 | `POST` | `/api/v1/auth/wechat/complete` | temp_token+手机号验证→完成注册 |
| 绑定微信 | `POST` | `/api/v1/auth/bind/wechat` | 已登录用户绑定微信（需鉴权） |
| 解绑微信 | `DELETE` | `/api/v1/auth/bind/wechat` | 已登录用户解绑微信（安全检查：至少保留一种登录方式） |
| 设置密码 | `POST` | `/api/v1/auth/password` | 无密码用户补设/已有密码用户修改（需鉴权） |
| 刷新令牌 | `POST` | `/api/v1/auth/refresh` | Token Rotation：旧 Token RENAME 钓鱼，签发新对 |
| 用户登出 | `POST` | `/api/v1/auth/logout` | 拔除关联 Session 族谱的所有 Token |

### C端用户领域 (Users)

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 查询个人信息 | `GET` | `/api/v1/users/me` | 需鉴权，直接返回当前用户 |
| 更新个人资料 | `PATCH` | `/api/v1/users/me` | 需鉴权，支持改密码/手机号/邮箱，含唯一性校验 |
| 注销账户 | `DELETE` | `/api/v1/users/me` | 需鉴权，软删除 (is_deleted + deleted_at) |

### B端管理员领域 (Admin)

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 管理员登录 | `POST` | `/api/v1/admin/login` | 用户名+密码，签发带 `aud=backend` 的双 Token |
| 管理员令牌刷新 | `POST` | `/api/v1/admin/refresh` | B端独立 Token Rotation (Redis Key 前缀隔离) |
| 管理员登出 | `POST` | `/api/v1/admin/logout` | 销毁 B端会话族谱 |
| 获取管理员信息 | `GET` | `/api/v1/admin/me` | 返回角色列表 + 权限码数组 (供 React 动态渲染菜单) |

### C端会员等级与钱包领域 (User Levels / Wallets)

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 查询等级体系 | `GET` | `/api/v1/user_levels/` | C端查看等级规则列表与权益对比 |
| 我的余额 | `GET` | `/api/v1/user_wallets/balance` | 实时余额 + 积分 |
| 余额流水 | `GET` | `/api/v1/user_wallets/balance/log` | 余额变动记录分页 |
| 积分流水 | `GET` | `/api/v1/user_wallets/points/log` | 积分变动记录分页 |
| B端充值/扣款 | `POST` | `/api/v1/admin/user_wallets/adjust` | 管理员手动调整余额/积分（RBAC 鉴权） |

### C/B端商品体系 (Products)

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 分类树 | `GET` | `/api/v1/products/categories` | 三级嵌套树形结构 |
| 商品列表 | `GET` | `/api/v1/products/` | 支持分类/类型/关键词筛选 |
| 商品详情 | `GET` | `/api/v1/products/{id}` | 含 SKU / 规格 / 实时会员价 |
| 上报浏览足迹 | `POST` | `/api/v1/products/{id}/view` | BackgroundTask 异步静默埋点 |
| 我的足迹 | `GET` | `/api/v1/products/my-views/list` | 防重历史时间线 |
| B端商品 CRUD | `POST/PATCH/DELETE` | `/api/v1/admin/products/` | 商品全生命周期管理 |
| B端 SKU/规格管理 | `PUT` | `/api/v1/admin/products/{id}/skus` | 批量替换 SKU / 规格模板 |
| B端等级价管理 | `PUT` | `/api/v1/admin/products/{id}/level-prices` | 多层级固定价设置 |
| B端独立分佣 | `PUT` | `/api/v1/admin/products/{id}/level-commissions` | SKU 级/商品级分佣规则 |

### B端媒体素材库 (Media)

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 上传图片 | `POST` | `/api/v1/admin/media/upload` | AOT 派生策略：自动生成 `_large` (1080px) 和 `_thumb` (400px)，保留原图 |
| 素材列表 | `GET` | `/api/v1/admin/media/` | 素材库查询（仅管理员） |
| 删除素材 | `DELETE` | `/api/v1/admin/media/{id}` | 物理删除文件 + 数据库记录 |

> 图片存储：`LocalStorageProvider` 挂载至 `uploads/` 目录，通过 `StaticFiles` 暴露。数据库仅存相对路径 `file_key`，URL 由 Service 层动态拼接（未来迁移 OSS/S3 零改动）。

### C端购物车 (Carts)

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 加入购物车 | `POST` | `/api/v1/carts/` | 双轨（登录用户/游客 `X-Device-Id`），自动合并同款数量 |
| 展开购物车 | `GET` | `/api/v1/carts/my` | 含实时价格探测、is_valid 下架检测、库存预警 |
| 调整条目 | `PATCH` | `/api/v1/carts/{id}` | 修改数量或勾选状态 |
| 批量删除 | `DELETE` | `/api/v1/carts/` | 按 ID 数组移出 |
| 游客车并网 | `POST` | `/api/v1/carts/merge` | 已登录后触发：将匿名设备车数据并入实名账号（含叠加/过户算法） |

### C端收货地址 (Addresses)

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 新建地址 | `POST` | `/api/v1/addresses/` | 首条自动设为默认，含 20 条容量上限 |
| 地址列表 | `GET` | `/api/v1/addresses/` | 默认地址排第一 |
| 默认地址 | `GET` | `/api/v1/addresses/default` | 结算页快捷预填充 |
| 修改地址 | `PUT` | `/api/v1/addresses/{id}` | 全量修改，可同步切换默认 |
| 设置默认 | `PATCH` | `/api/v1/addresses/{id}/set-default` | 互斥引擎：原子事务保证唯一默认 |
| 删除地址 | `DELETE` | `/api/v1/addresses/{id}` | 物理删除；若删的是默认，自动晋升最早创建的地址 |

### B端收货地址管理 (Addresses Admin)

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 地址查询 | `GET` | `/api/v1/admin/addresses/` | 分页查询全部用户地址，支持按 user_id 精确过滤 |

---

### 数据模型一览

| 表名 | 所属端 | 用途 | 关键设计 |
|------|--------|------|---------|
| `users` | C端 | 买家核心账号 | phone_code+mobile 唯一，密码可选 |
| `user_socials` | C端 | 三方绑定 | platform+openid 唯一约束 |
| `user_level_rules` | C端 | 会员等级规则 | JSONB 升级条件，分佣奖励配置 |
| `user_level_profiles` | C端 | 用户等级档案 | 当前等级、累计消费、推荐关系 |
| `user_level_change_logs` | C端 | 等级变更日志 | 全量操作留痕 |
| `user_wallets` | C端 | 余额与积分账户 | DECIMAL(15,2)，双账户隔离 |
| `user_balance_logs` | C端 | 余额流水 | 不可变流水记录 |
| `user_point_logs` | C端 | 积分流水 | 不可变流水记录 |
| `sms_logs` | C端 | 短信审计 | IP+模板+流水号永久留存 |
| `sys_admins` | B端 | 管理员账号 | 独立于 users 表物理隔离 |
| `sys_roles` | B端 | 角色 | RBAC 五表结构 |
| `sys_permissions` | B端 | 权限点 | menu/button/api 三类 |
| `sys_admin_role` | B端 | 管理员-角色关联 | M:N |
| `sys_role_permission` | B端 | 角色-权限关联 | M:N |
| `sys_login_logs` | 双端 | 登录日志 | C端+B端所有登录事件 |
| `sys_audit_logs` | B端 | 管理员操作审计 | JSONB 请求体自动脱敏 |
| `categories` | C/B端 | 商品分类 | 三级限制，JSONB 等级折扣/分佣规则 |
| `products` | C/B端 | 商品 SPU | virtual/physical 双类型，软删除 |
| `product_categories` | C/B端 | 商品-分类关联 | M:N |
| `product_specs` | C/B端 | 规格模板 | 颜色/尺寸等规格名+候选值 |
| `product_skus` | C/B端 | SKU 变体 | 规格组合+独立售价+库存 |
| `product_level_prices` | C/B端 | 等级固定价 | SKU 级/商品级优先级 |
| `product_level_commissions` | C/B端 | 独立分佣规则 | 直推/间推/其它三档固定金额 |
| `media_assets` | B端 | 媒体素材 | file_key 相对路径，URL 动态拼接 |
| `product_views` | C端 | 商品浏览足迹 | user_id+product_id 联合唯一，UPSERT 防重 |
| `cart_items` | C端 | 购物车 | user_id/anonymous_id 双轨身份 |
| `addresses` | C端 | 收货地址 | 省市区文本+行政编码双存，is_default 互斥 |

> **架构红线**: C端 (`users`) 与 B端 (`sys_admins`) 物理隔离，严禁混表。所有模型继承自 `UUIDModel` (UUID v7 主键 + UTC 时间戳)。

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
| 多渠道认证 | 手机号锚点 + 密码/短信/小程序/网页扫码四入口，临时凭证5分钟过期+一次性使用 |
| 验证码安全 | 60秒发送冷却 + 5次错误自动锁定 + Redis原子操作 + 一次性消费 |
| 社交绑定安全 | platform白名单校验 + openid冲突检测 + 解绑前保留最后登录方式检查 |
| 软删除防复活 | 被注销手机号不可被重新注册，返回"已注销请联系客服" |
| B端全量审计 | `AuditLogMiddleware` 中间件拦截 `/admin/` 下所有请求（含 GET），旁路落库 `sys_audit_logs`，请求体自动脱敏 |
| 双端登录留痕 | `LoginLog` 记录 C端+B端所有登录事件（含 IP、UA、成功/失败原因） |
| 短信审计留痕 | `sms_logs` 表记录每条短信的发送状态、IP、模板ID、云平台流水号 |
| 令牌防盗用 | Token Family 族谱追踪 + Redis `RENAME` 钓鱼，窃用后立刻启动连坐销毁 |
| B/C 双轨隔离 | JWT `aud=backend` 标识 + Redis Key 前缀隔离 + 物理分表，两端凭证无法互通 |
| RBAC 权限控制 | 5 表模型 (SysAdmin/SysRole/SysPermission + 关联表) + `require_permission()` 工厂函数 |
| 防枚举攻击 | 登录失败统一返回 `auth.invalid_credentials`，不区分用户名/密码错误 |
| PII 脱敏 | 日志中自动过滤 password/token/card_number 等敏感字段 |
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

## 📝 C端业务实现进度

### 已完成 ✅

- [x] **多渠道聚合登录体系** — 手机号锚点 + 短信验证码 + 微信小程序 + 微信网页扫码。
- [x] **社交绑定/解绑管理** — 含冲突检测和安全检查。
- [x] **会员等级与分销体系** — 多层级分佣 + 升降级规则 + 推荐关系 + 变更日志。
- [x] **用户钱包** — 余额/积分双账户 + 流水记录 + B端调控管理接口。
- [x] **商品体系** — 三级分类树 + SPU/SKU + 5级价格引擎 + 3级分佣引擎。
- [x] **媒体素材管理** — LocalStorageProvider + AOT 多规格图片派生 + 素材库管理。
- [x] **商品浏览足迹** — 登录用户 UPSERT 去重足迹 + 50 条自动修剪 + 时间线展示。
- [x] **购物车** — 双轨（实名+游客 `X-Device-Id`）+ 合并算法 + 实时 5 级价格探测 + is_valid 下架检测。
- [x] **收货地址** — 省市区行政编码双存 + 默认地址互斥引擎 + 智能晋升 + `AddressSnapshot` 快照预留。

### 进行中 / 待开发 🚧

- [ ] **订单结算域 (Checkout → Order)** — 基于购物车勾选 + 地址快照 + 库存锁定的下单流。
- [ ] **支付域** — 微信支付 / 余额支付接入，支付回调与状态机管理。
- [ ] **物流域** — 顺丰/菜鸟行政编码对接，物流轨迹追踪。
- [ ] **修改手机号流程** — 旧手机+新手机双重验证码验证。
- [ ] **腾讯云 SMS 正式签名** — TC3-HMAC-SHA256 算法上线前需补全。
- [ ] **单元自动化覆盖** — PyTest + 安全防线压测。

---

## 📄 License

MIT © [jinmozhe](https://github.com/jinmozhe)
