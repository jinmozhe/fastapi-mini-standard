# 系统架构 (ARCHITECTURE)

## 架构模式

**分层领域驱动架构** (Layered DDD) — 严格分层 + 领域独立

```
Router → Service → Repository → ORM Model
  ↑         ↑           ↑            ↑
Schema  AppException  Session    Base/Mixin
```

### 层级职责

| 层级 | 职责 | 位置 |
|---|---|---|
| **Router** | HTTP 端点, 请求/响应序列化, 依赖注入组装 | `app/domains/{domain}/router.py` |
| **Service** | 业务逻辑编排, 事务提交, 业务规则校验 | `app/domains/{domain}/service.py` |
| **Repository** | 数据访问封装, SQL 构建, 过滤软删除 | `app/domains/{domain}/repository.py` 或 `app/db/repositories/` |
| **Model** | ORM 映射, 表结构定义 | `app/db/models/` |
| **Schema** | Pydantic 输入/输出验证, OpenAPI 文档 | `app/domains/{domain}/schemas.py` |
| **Core** | 横切关注点 (配置/安全/日志/异常/中间件) | `app/core/` |

### 分层约束 (import-linter 强制执行)

```
app.core           (顶层 - 基础设施)
app.db.models      (ORM 模型层)
app.db.repositories (仓储层)
app.domains         (领域层)
app.services        (跨域服务层)
app.api             (API 层)
```

- **领域独立性**: `app.domains.users` ⇎ `app.domains.auth` (禁止直接导入)
- **Service 禁止导入 ORM**: `app.domains.*.service` → `app.db.models` ✗
- **无循环依赖**: `app.domains` 内部无环

> 注意: 当前代码中 `auth.service` 直接导入了 `app.db.models.user` 和 `app.db.models.log`, 这似乎与 import-linter 规则存在潜在冲突。

## 数据流

### 请求处理流程

```
客户端请求
  ↓
[CORS Middleware]     → 跨域过滤
  ↓
[AuditLogMiddleware]  → 审计日志记录
  ↓
[RequestLogMiddleware] → UUID v7 Request ID 注入 + 访问日志
  ↓
[Router]              → 参数校验 (Pydantic) + 依赖注入
  ↓
[Service]             → 业务逻辑 + 事务控制
  ↓
[Repository]          → SQL 查询 + 数据持久化
  ↓
[DB/Redis]            → 数据存储
  ↓
ResponseModel.success/fail → 统一响应信封
```

### 认证流程

```
POST /auth/login
  ↓
AuthService.login()
  ↓
UserRepository.get_by_phone_number()  → 查用户
  ↓
verify_password_async()               → 校验密码 (Argon2id)
  ↓
create_access_token()                 → JWT Access Token
secrets.token_urlsafe()               → Refresh Token
  ↓
Redis.setex("refresh_token:xxx")      → 存储 Refresh Token
  ↓
返回 Token 响应
```

### JWT 验签流程

```
请求携带 Authorization: Bearer <token>
  ↓
get_token_from_header()    → 提取 token
  ↓
jwt.decode()               → 验签 + 提取 sub (user_id)
  ↓
session.get(User, user_id) → 查库确认
  ↓
检查: is_deleted / is_active → 状态校验
  ↓
返回 User 对象 → 注入到 endpoint
```

## 核心抽象

### 1. ORM 模型组件化 (Mixin)

```
Base (DeclarativeBase)
  └── UUIDBase (__abstract__)
        ├── id: UUID v7 主键
        ├── __tablename__: 自动 snake_case
        ├── update(**kwargs): 动态属性更新
        └── UUIDModel (UUIDBase + TimestampMixin, __abstract__)
              ├── created_at / updated_at (UTC)
              └── 可组合 SoftDeleteMixin → is_deleted / deleted_at
```

### 2. 通用 Repository (CRUD)

```python
class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    PROTECTED_FIELDS = {"id", "created_at", "updated_at"}
    # get(id) / exists(id) / list(skip, limit) / count()
    # create(schema) / update(obj, schema_or_dict) / delete(id)
```

### 3. 统一响应信封

```python
class ResponseModel(Generic[T]):
    code: str          # "success" 或 "domain.reason"
    message: str       # 人类可读消息
    data: T | None     # 业务数据泛型
    request_id: str    # 请求追踪 ID
    timestamp: datetime # UTC 时间戳
```

### 4. 错误码体系

```python
class BaseErrorCode(Enum):
    value = (http_status, code_string, default_message)
    # 属性: .http_status / .code / .msg

class AppException(Exception):
    def __init__(self, error: BaseErrorCode, message="", data=None)
```

### 5. 依赖注入链

```
get_db() → AsyncSession          (DBSession 别名)
get_redis() → Redis              (Redis 客户端)
get_token_from_header() → str    (JWT Token)
get_current_user() → User        (CurrentUser 别名)
get_current_superuser() → User   (SuperUser 别名)
```

## 入口点

| 入口 | 文件 | 说明 |
|---|---|---|
| **应用入口** | `app/main.py` | `create_app()` 工厂函数 → `app = create_app()` |
| **Uvicorn 启动** | `app/main.py:130` | `uvicorn.run(app, ...)` (调试模式) |
| **路由聚合** | `app/api_router.py` | 聚合所有领域 router → `api_router` |
| **Alembic 迁移** | `alembic/env.py` | 数据库迁移环境 |
| **健康检查** | `/pinjie/health` | K8s Liveness/Readiness Probe |

## 应用生命周期 (Lifespan)

```python
@asynccontextmanager
async def lifespan(app):
    setup_logging()     # 启动: 初始化日志
    yield
    await close_redis() # 关闭: 释放 Redis
    await engine.dispose() # 关闭: 释放 DB 连接池
```
