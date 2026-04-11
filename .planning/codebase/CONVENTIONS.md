# 编码规范 (CONVENTIONS)

## 代码风格

### Python 版本特性

- **最低要求**: Python 3.11+
- **类型注解**: 原生 `X | None` 语法 (非 `Optional[X]`)
- **泛型**: 使用 `Generic[T]` 配合 `TypeVar`
- **集合类型**: `list[str]`, `dict[str, Any]` (非 `List`, `Dict`)
- **导入规范**: `from collections.abc import AsyncGenerator` (非 `typing`)

### 格式化

- **工具**: Ruff (格式化 + Lint 合一)
- **行宽**: 88 字符
- **引号**: 双引号 (`"`)
- **缩进**: 空格

### 注释规范

- **语言**: 所有代码注释和文档字符串使用**中文**
- **文件头**: 每个源文件包含标准文件头 (File / Description / Author / Created)
- **内联注释**: 使用 `#` 后空格, 解释 "why" 而非 "what"
- **常量注释**: 核心常量行尾附带中文说明

### 文件头模板

```python
"""
File: app/{module}/{name}.py
Description: 模块功能简述

本模块负责：
1. 职责一
2. 职责二

Author: jinmozhe
Created: YYYY-MM-DD
Updated: YYYY-MM-DD (vX.Y: 变更说明)
"""
```

## 编码模式

### 1. 依赖注入模式 (Annotated + Depends)

```python
# 定义
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

# 别名
DBSession = Annotated[AsyncSession, Depends(get_db)]

# 使用
async def endpoint(session: DBSession): ...
```

**依赖链组装** (每个领域的 `dependencies.py`):

```python
# 3 层: DB → Repository → Service → ServiceDep
UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
```

### 2. 错误码枚举模式

```python
class AuthError(BaseErrorCode):
    """认证领域错误 — Tuple: (HTTP状态, 字符串码, 默认消息)"""
    INVALID_CREDENTIALS = (HTTP_403_FORBIDDEN, "auth.invalid_credentials", "账号或密码错误")

# 使用
raise AppException(AuthError.INVALID_CREDENTIALS)
raise AppException(AuthError.PHONE_EXIST, message="自定义覆盖消息")
```

### 3. 统一响应信封模式

```python
# 成功
return ResponseModel.success(data=user, message="操作成功", request_id=req_id)

# 失败 (由异常处理器自动构造)
ResponseModel.fail(code=exc.code, message=exc.message, request_id=request_id)
```

### 4. Repository 泛型模式

```python
class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    """扩展特定查询, 默认继承 CRUD"""
    async def get_by_phone_number(self, phone: str) -> User | None:
        stmt = select(User).where(User.phone_number == phone, User.is_deleted.is_(False))
        ...
```

### 5. Service 事务控制模式

```python
class UserService:
    async def update(self, user_id, obj_in):
        # 1. 查询验证
        user = await self.get(user_id)
        # 2. 业务规则校验
        if duplicate: raise AppException(UserError.PHONE_EXIST)
        # 3. 调用 Repository 更新
        updated = await self.repo.update(user, update_data)
        # 4. Service 层负责 commit
        await self.repo.session.commit()
        await self.repo.session.refresh(updated)
        return updated
```

### 6. Router 端点模式

```python
@router.post("/login", response_model=ResponseModel[Token], summary="用户登录")
async def login(request: Request, data: LoginRequest, service: AuthServiceDep) -> ResponseModel[Token]:
    token = await service.login(data)
    req_id = getattr(request.state, "request_id", None)
    return ResponseModel.success(data=token, message=AuthMsg.LOGIN_SUCCESS, request_id=req_id)
```

### 7. ORM 模型组合模式

```python
# 标准业务表 (90% 场景)
class User(UUIDModel, SoftDeleteMixin): ...

# 简单关联表 (无时间戳)
class OrderItem(UUIDBase): ...
```

## 错误处理

### 异常层级

```
Exception
  └── AppException (业务异常)
        → 由 app_exception_handler 捕获
        → 映射为: 语义化 HTTP 状态码 + 字符串业务码 + 统一信封

FastAPI RequestValidationError (参数校验)
  → 由 validation_exception_handler 捕获
  → HTTP 400 + "system.invalid_params"

Starlette HTTPException (框架 HTTP 异常)
  → 由 http_exception_handler 捕获
  → 保留原始 HTTP 状态码

Exception (未捕获异常 — 最后防线)
  → 由 general_exception_handler 捕获
  → HTTP 500 + "system.internal_error"
  → 完整堆栈记录到日志
```

### 异常处理要点

- `from None` 截断异常链 (防止泄露内部库信息)
- `logger.opt(exception=exc)` 记录完整堆栈
- 500 错误对外屏蔽内部细节, 仅返回通用消息
- 所有异常日志绑定 `request_id`

## 异步模式

- **全异步**: 所有 DB 操作通过 `AsyncSession` + `asyncpg`
- **CPU 密集**: 密码哈希通过 `run_in_threadpool()` 包装
- **Session 规则**: `expire_on_commit=False` + `autoflush=False`
- **事务控制**: Service 层负责 `commit()`, Repository 层仅 `flush()`
- **连接管理**: `async with AsyncSessionLocal()` 自动关闭

## 类型安全

- `disallow_untyped_defs = true` (Mypy 强制)
- `# type: ignore[arg-type]` 仅用于已知安全的类型缩窄场景
- `cast(Any, data)` 解决 Pylance 在泛型场景下的误报
- Pydantic `ConfigDict(from_attributes=True)` 启用 ORM → Schema 转换
