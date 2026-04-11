# ARCHITECTURE.md — 系统架构

## 架构模式
**分层领域驱动架构 (Layered DDD-lite)** + **依赖注入 (DI via FastAPI Depends)**

严格禁止跨层越级调用，由 `import-linter` 在 CI 层面强制执行。

## 层次结构

```
请求入口
  ↓
[API Layer]     app/api/deps.py          — 全局依赖（DB Session, Auth, Permission）
                app/api_router.py        — 路由聚合器
  ↓
[Domain Layer]  app/domains/{name}/      — 每个领域独立封装
                ├── router.py            — HTTP 端点定义
                ├── schemas.py           — Pydantic 输入/输出模型
                ├── service.py           — 业务逻辑编排
                ├── repository.py        — 数据访问（继承 BaseRepository）
                └── constants.py         — 领域错误码 + 消息常量
  ↓
[Core Layer]    app/core/                — 横切关注点
                ├── config.py            — 配置管理（pydantic-settings）
                ├── security.py          — 密码哈希 + JWT
                ├── exceptions.py        — 异常类 + 全局处理器
                ├── error_code.py        — 错误码枚举基类
                ├── response.py          — 统一响应信封
                ├── middleware.py         — 中间件（RequestID, CORS, AccessLog）
                ├── logging.py           — Loguru 配置
                └── redis.py             — Redis 连接管理
  ↓
[DB Layer]      app/db/
                ├── models/base.py       — ORM 基类（UUIDBase, UUIDModel, Mixins）
                ├── models/user.py       — 用户模型
                ├── repositories/base.py — 通用仓储基类（CRUD 泛型）
                └── session.py           — 异步引擎 + 会话工厂
```

## 数据流

```
Client Request
  → CORSMiddleware
  → RequestLogMiddleware (生成 request_id, 绑定 Loguru 上下文)
  → FastAPI Router (路由匹配)
  → Depends 依赖链 (get_db → get_token_from_header → get_current_user)
  → Domain Router → Domain Service → Repository → DB
  → ResponseModel.success() / AppException → ExceptionHandler
  → ORJSONResponse (统一信封)
```

## 认证流程
- **方式**: Header Bearer Token（非 Cookie）
- **Access Token**: JWT（HS256），短效（30 分钟），无状态
- **Refresh Token**: 随机高熵字符串，存 Redis（7 天 TTL），Token Rotation 策略
- **权限层级**: `CurrentUser` → `SuperUser`（通过 Depends 链组合）

## ORM 模型继承体系

```
Base (DeclarativeBase)
  └── UUIDBase (UUID v7 主键 + 自动蛇形表名 + update() 方法)
        └── UUIDModel (+ TimestampMixin: created_at, updated_at)
              └── User (+ SoftDeleteMixin: is_deleted, deleted_at)
```

- 字段排序规范: `id` (sort_order=-100) → 业务字段 (默认 0) → 时间戳 (100-101) → 软删除 (102-103)
- 约束命名规范: `POSTGRES_INDEXES_NAMING_CONVENTION`（如 `ix_表名_列名`, `uq_表名_列名`）
- **No-Relationship 模式**: 不使用 ORM relationship，关联查询在 Repository 层用 JOIN 实现

## 统一响应信封
```json
{
  "code": "success | domain.reason",
  "message": "人类可读消息",
  "data": {},
  "request_id": "uuid-v7",
  "timestamp": "2026-04-11T..."
}
```
