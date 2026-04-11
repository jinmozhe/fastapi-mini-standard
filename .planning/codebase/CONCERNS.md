# 关注点与技术债务 (CONCERNS)

## 🔴 高优先级问题

### 1. 不存在的模型文件被引用

**文件**: `app/db/models/__init__.py`

```python
from app.db.models.user_profile import UserProfile   # ❌ 文件不存在
from app.db.models.user_social import UserSocial       # ❌ 文件不存在
from app.db.models.log import LoginLog, OperationLog   # ❌ 文件不存在
```

`__init__.py` 导入了 3 个不存在的模型模块 (`user_profile.py`, `user_social.py`, `log.py`)。这会导致 **应用启动时 ImportError 崩溃**。

**影响**: 应用无法启动；Alembic 迁移无法执行。
**修复**: 要么创建缺失的模型文件, 要么移除未实现的导入。

### 2. 不存在的 Admin 领域被引用

**文件**: `app/api_router.py`

```python
from app.domains.admin.router import router as admin_router  # ❌ 目录不存在
```

`api_router.py` 引用了 `app.domains.admin`, 但 `app/domains/` 下只有 `auth/` 和 `users/`。同样会导致 **ImportError**。

**影响**: 应用无法启动。
**修复**: 创建 admin 领域或移除该路由注册。

### 3. 不存在的 AuditLogMiddleware 被引用

**文件**: `app/core/middleware.py`

```python
from app.core.audit import AuditLogMiddleware  # ❌ 文件不存在
```

中间件模块导入了不存在的 `app/core/audit.py`。会导致 **ImportError**。

**影响**: 应用无法启动。
**修复**: 创建该模块或移除导入。

### 4. Repository 引用不存在的 Schema

**文件**: `app/domains/users/repository.py`

```python
from app.domains.users.schemas import UserCreate, UserUpdate
```

`UserCreate` 类在 `app/domains/users/schemas.py` 中**不存在** (已被移到 `auth/schemas.py` 的 `RegisterRequest`)。会导致 **ImportError**。

**影响**: 用户领域功能无法正常工作。
**修复**: 移除 `UserCreate` 导入或创建该 Schema 类。

## 🟡 中优先级问题

### 5. import-linter 规则与实际代码不一致

**文件**: `.importlinter`

- 规则中列出了 `app.domains.orders`, `app.domains.products`, `app.domains.inventory` — 这些领域目录均不存在
- 实际只有 `app.domains.auth` 和 `app.domains.users`
- `auth.service` 直接导入了 `app.db.models.user` 和 `app.db.models.log`，违反了 `no_orm_in_service` 规则

**影响**: `lint-imports` 命令可能报错或规则失效。
**修复**: 更新 `.importlinter` 配置以反映实际领域结构。

### 6. Auth 领域缺少 `__init__.py` 和 `dependencies.py`

**目录**: `app/domains/auth/`

与 `users` 领域相比, `auth` 领域:
- 缺少 `__init__.py` (虽然不影响运行, 但不符合项目约定)
- 缺少 `dependencies.py` (依赖注入直接写在 `router.py` 中)
- 缺少 `repository.py` (直接复用 `UserRepository`)

**影响**: 架构一致性降低, 不符合领域模块标准结构。
**修复**: 为 auth 领域补充标准化的模块文件。

### 7. Dockerfile 和 docker-compose.yml 为空

**文件**: `Dockerfile`, `docker-compose.yml`

两个容器化文件内容为空, 仅占位。无法进行 Docker 构建和编排。

**影响**: 无法容器化部署。
**修复**: 实现多阶段 Docker 构建和 PG + Redis + App 编排。

### 8. 测试目录缺失

**目录**: `tests/`

`pyproject.toml` 配置了 `testpaths = ["tests"]`, 但 `tests/` 目录不存在, 也没有任何测试文件。

**影响**: 无法运行测试, 代码质量无保障。
**修复**: 创建测试目录和基础测试用例。

## 🟢 低优先级 / 改进建议

### 9. UserRead Schema 包含未定义字段

**文件**: `app/domains/users/schemas.py`

`UserBase` 定义了 `full_name` 字段, 但 `User` ORM 模型中没有对应列。`UserRead` 继承 `UserBase`, 因此 `full_name` 会出现在 API 响应 Schema 中, 但实际永远为 `None`。

### 10. LoginLog.user_id 类型不一致

**文件**: `app/domains/auth/service.py`

```python
login_log = LoginLog(user_id=user_id_for_log if user_id_for_log else "Unknown", ...)
```

当登录失败时, `user_id` 存储字符串 `"Unknown"` — 如果 LoginLog 模型定义 user_id 为 UUID 类型, 这将引发运行时错误。

### 11. 密码安全增强

当前 `UserUpdate` schema 允许通过 PATCH `/users/me` 直接修改密码, 无需提供旧密码验证。生产环境应增加旧密码校验步骤。

### 12. CORS 配置

```python
allow_methods=["*"]
allow_headers=["*"]
```

生产环境应限制允许的 HTTP 方法和 Headers, 而非使用通配符。

### 13. services/ 包为空

`app/services/__init__.py` 是空文件。如果跨域调用需求出现, 需在此处实现协调服务。

### 14. 缺少 pre-commit 配置文件

`pyproject.toml` 声明了 `pre-commit>=3.7.0` 依赖, 但项目根目录没有 `.pre-commit-config.yaml` 文件。

## 安全关注

| 项目 | 状态 | 说明 |
|---|---|---|
| 密码哈希 | ✅ | Argon2id (pwdlib), 异步执行 |
| JWT 签名 | ✅ | HS256, 可配置密钥 |
| Token 旋转 | ✅ | Refresh Token 一次性使用 |
| 密钥强度 | ✅ | 生产环境强制 >=32 字符 |
| 软删除用户拦截 | ✅ | 验签后查库校验 is_deleted |
| SQL 注入 | ✅ | SQLAlchemy 参数化查询 |
| 异常信息泄露 | ✅ | 500 错误屏蔽内部堆栈 |
| 混淆文档路径 | ✅ | `/pinjie/*` 前缀 |
| PII 脱敏 | ✅ | `utils/masking.py` |
| 登录暴力破解 | ⚠️ | 无速率限制或账号锁定 |
| CORS 通配符 | ⚠️ | 生产环境需收紧 |
