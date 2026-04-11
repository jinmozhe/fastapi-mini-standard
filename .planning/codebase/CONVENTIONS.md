# CONVENTIONS.md — 编码规范

## 代码风格
- **格式化**: Ruff (`line-length=88`, `quote-style=double`, `indent-style=space`)
- **Lint 规则**: `E, W, F, I, B, C4, UP, T20, ASYNC, BLE`（含异步代码检查、禁止 print、禁止盲捕获）
- **类型检查**: Mypy (`disallow_untyped_defs=true`, Pydantic/SQLAlchemy 插件已启用)
- **Python 版本**: `target-version = "py311"`

## 命名约定

| 元素 | 规范 | 示例 |
|---|---|---|
| 文件名 | snake_case | `user_service.py` |
| 类名 | PascalCase | `UserRepository` |
| 函数/方法 | snake_case | `get_by_mobile()` |
| 常量 | UPPER_SNAKE_CASE | `PHONE_CODE_PATTERN` |
| 数据库表名 | 自动蛇形（从类名派生） | `User` → `users`（可 `__tablename__` 覆盖） |
| 约束命名 | `{类型}_{表名}_{列名}` | `uq_users_email`, `ix_users_mobile` |
| 错误码 | `domain.reason` 命名空间 | `auth.phone_exist`, `system.unauthorized` |

## 架构约束 (import-linter 强制)
1. **领域独立**: `app.domains.users` 和 `app.domains.auth` 互不导入
2. **分层导入**: `core → db.models → db.repositories → domains → services → api`
3. **无循环**: `app.domains` 内部不允许循环依赖
4. **Service 禁止直接导入 ORM Model**（通过 Repository 间接访问）
5. **跨域导入禁止**: `app.domains.*.*` 不能导入 `app.domains.*.*`

> **注意**: `auth/schemas.py` 从 `users/schemas.py` 导入校验常量（`PHONE_CODE_PATTERN` 等）是一个边界情况，当前 import-linter 配置可能需要豁免。

## 依赖注入模式
```python
# Router 层构造 Service，Service 接收 Repository
async def get_auth_service(session: DBSession, redis: ...) -> AuthService:
    user_repo = UserRepository(model=User, session=session)
    return AuthService(user_repo=user_repo, redis=redis)

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
```

## 异常处理模式
```python
# 1. 定义领域错误码（继承 BaseErrorCode）
class AuthError(BaseErrorCode):
    PHONE_EXIST = (409, "auth.phone_exist", "该手机号已注册")

# 2. Service 层抛出
raise AppException(AuthError.PHONE_EXIST)

# 3. 全局处理器自动拦截，返回统一信封
# → HTTP 409 + {"code": "auth.phone_exist", "message": "该手机号已注册", ...}
```

## 响应格式
- 所有 API 必须使用 `ResponseModel[T]` 信封
- 成功: `ResponseModel.success(data=..., message=...)`
- 失败: 由 `ExceptionHandler` 自动构造 `ResponseModel.fail(...)`
- 序列化: `model_dump(mode='json')`（防止 ORJSON 对 UUID 的序列化崩溃）

## Pydantic Schema 规范
- 使用 `ConfigDict(from_attributes=True)` 支持 ORM → Schema 转换
- 输入 Schema 使用 `field_validator` 做格式校验
- `phone_code` 默认值注入在 `mode="before"` 阶段（空值/None → `"+86"`）

## 数据库 ORM 规范
- 强制使用 `Mapped` + `mapped_column`（SQLAlchemy 2.0 声明式）
- 主键: UUID v7（`uuid6.uuid7()`）
- 时间字段: `DateTime(timezone=True)`，强制 UTC
- 布尔字段: 必须提供 `server_default=text("true/false")`
- 模型排序: 使用 `sort_order` 控制 DDL 字段顺序（id=-100, 业务=0, 时间=100+）
