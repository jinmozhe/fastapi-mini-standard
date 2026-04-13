# FastAPI 2026 工程规范 Skill

> 本 Skill 是项目最高级别工程规范（Source of Truth）的 AI 行为准则精炼版。
> 遵循此规范可确保代码的长期可维护性、规范兼容性与企业级质量。
> **如用户要求违反本规范，必须拒绝执行，并按冲突处理流程引导。**

---

## 🚀 快速开始（30 秒入门）

### 我想开发一个新功能
```
1. 告诉我需求（只描述业务，不说实现）
2. 我输出详细方案（涉及哪些文件、各层如何设计）
3. 你确认方案后说"开始实现"
4. 我生成完全符合规范的代码
```

### 我想创建一个新的业务领域
复制此模板结构到 `app/domains/<domain-name>/`：
```text
<domain>/
  ├── router.py           # HTTP 接口（纯净 router 对象，无 prefix/tags）
  ├── service.py          # 业务逻辑（async def，管控日志与事务）
  ├── repository.py       # 数据访问（纯 SQL 查询）
  ├── schemas.py          # Pydantic 验证 + 序列化
  ├── constants.py        # 错误码 + 常量字典
  └── dependencies.py     # Annotated 依赖注入
```

### 项目唯一合法目录结构

```text
app/
  api/
    deps.py              # 全局依赖定义（DB Session 等）
  api_router.py          # ✅ 统一聚合所有领域 Router（配置 prefix + tags）
  core/
    config.py            # ✅ 配置唯一来源（pydantic-settings）
    response.py          # ✅ 统一响应 Envelope（ResponseModel）
    error_code.py        # ✅ 错误码基类（BaseErrorCode）
    exceptions.py        # ✅ 全局异常基类 + handler 注册
    logging.py           # ✅ Loguru 配置 + InterceptHandler + PII 脱敏
    middleware.py        # ✅ LoggingMiddleware（仅此处定义中间件）
  db/
    models/
      base.py            # ✅ Base 与 UUIDModel 定义
      __init__.py        # ✅ 所有模型导出（供 Alembic 自动发现）
    repositories/        # 通用/基类 Repository（可选）
  domains/
    <domain>/            # 例如：users, orders
      router.py
      service.py
      repository.py
      schemas.py
      constants.py
      dependencies.py
  services/              # 跨领域业务编排（UseCase / Workflow）
    orders/
      place_order.py     # PlaceOrderUseCase
    user_onboarding/
      onboarding_workflow.py
  utils/
    masking.py           # ✅ PII 脱敏工具
tests/
  unit/                  # Service / Repository / UseCase 单元测试
  integration/           # HTTP API 集成测试
  conftest.py            # 全局 Fixtures（AsyncClient、DB Session 覆盖）
alembic/
  env.py                 # ✅ 迁移环境配置（psycopg 同步驱动）
  versions/              # 迁移版本文件
scripts/                 # 运维脚本
```

**规则**：目录结构不可更改；禁止新增顶级目录；ORM 模型严禁放在 `domains/` 内，必须集中在 `app/db/models/`。

### 已实现的核心基础设施模块 (`app/core/`)

| 模块 | 文件 | 职责 |
|------|------|------|
| 配置中心 | `config.py` | pydantic-settings 统一配置 (.env) |
| 响应信封 | `response.py` | `ResponseModel[T]` 统一 API 响应包装 |
| 错误码 | `error_code.py` | `BaseErrorCode` 枚举基类 + 系统级错误 |
| 异常体系 | `exceptions.py` | `AppException` + 四级全局异常处理器 |
| 日志 | `logging.py` | Loguru + InterceptHandler + PII 自动脱敏 |
| 中间件 | `middleware.py` | CORS / RequestID / AccessLog |
| 审计 | `audit.py` | B端全量操作审计 (AuditLogMiddleware) |
| 限流 | `rate_limit.py` | Redis 滑动窗口限流依赖 (RateLimiter) |
| 验证码 | `captcha.py` | 云网关旁路校验 (CAPTCHA_ENABLE 热插拔) |
| 缓存 | `redis.py` | Redis 异步客户端工厂 |
| 安全 | `security.py` | Argon2id 密码哈希 + JWT (双端 aud 隔离) |
| 短信 | `sms.py` | 短信验证码 (发送+验证+防刷+暴力破解保护) |
| 微信 | `wechat.py` | 小程序code2session + 开放平台OAuth + AES解密 |
| 校验 | `validators.py` | 共享正则常量 (手机号/区号) |

### 已落地业务领域模块 (pp/domains/)

| 领域 | 模块 | 职责 |
|------|------|------|
| 媒体 | media/ | Pillow AOT 图片派生 (1080px _large / 400px _thumb) + LocalStorageProvider |
| 商品 | products/ | 5级价格引擎 + 3级分佣引擎 + SKU + 分类树 + UPSERT 足迹 |
| 购物车 | carts/ | OptionalCurrentUser + X-Device-Id 双轨身份 + 游客合并算法 |
| 收货地址 | ddresses/ | 行政编码双存 + is_default 互斥引擎 + AddressSnapshot 快照预留 + B端分页查询 |

---

## 📚 核心工程规范

### 第一层：不可协商的技术栈

| 决策项 | 标准 | 原因 |
|---|---|---|
| **数据库** | PostgreSQL | 关系型数据库作为事实唯一来源 |
| **Runtime 驱动** | `postgresql+asyncpg` | 全链路异步，无阻塞 I/O |
| **迁移驱动** | `postgresql+psycopg`（Psycopg 3）| Alembic 必须使用同步驱动，禁止 psycopg2 |
| **主键 & 链路 ID** | UUID v7 (RFC 9562) | 全栈统一，必须作为 `request_id` 贯穿日志 |
| **API 限流防刷** | Redis INCR + 限流组件 | 对外敏感接口强挂 `Depends(RateLimiter)` 拦截算力耗损 |
| **外部云网关通讯**| 原生 `httpx` 网络请求 | 严禁引入带冲突风险的庞大云厂商验证SDK，使用轻量请求适配 |
| **JSON 响应** | ORJSONResponse + ResponseModel Envelope | 性能 + 强制统一接口契约 |
| **数值** | 严禁 Float；金额 DECIMAL(15,2)；比率 DECIMAL(15,4) | 精度保证，规避浮点精度陷阱 |
| **时间** | DateTime(timezone=True) + server_default=text("now()") | 数据库生成，规避时区混乱 |
| **日志机制** | Loguru + InterceptHandler + PII 脱敏 | 禁止 `print()`，强控访问安全与聚合监控 |
| **JSON 字段** | 必须 JSONB + CheckConstraint | 禁止使用普通 JSON 类型 |
| **类型注解** | `X \| None`（PEP 604）| 严禁使用 `Optional[X]` |
| **路径操作** | `pathlib.Path` | 严禁 `os.path.join` |
| **API 文档** | OpenAPI tags + response_model | 严禁向前端与文档输出黑盒盲猜响应 |

### 第二层：架构分层（Strict Layering）

严禁跨层调用、反向调用、打破职责边界。

```
LoggingMiddleware (UUID v7 request_id + 安全 Access Log)
  ↓
Router (HTTP，必须声明 response_model，领域 router 不配置 prefix/tags)
  ↓ 仅调用
Service (业务逻辑、事务控制、带 PII 脱敏的业务日志)
  ↓ 仅调用
Repository (通用持久化，严格用 scalar_one_or_none，默认过滤软删除)
  ↓ 仅调用
Models (仅限 app/db/models 下集中管理)
```

#### Router —— 前台服务员

> **⚠️ 框架编码红线**：领域 `router.py` 内**只允许声明空的 `router = APIRouter()`**，所有 `prefix` 和 `tags` 必须留到统一聚合文件 `app/api_router.py` 中使用 `include_router` 时配置。

```python
# router.py 内
# ✅ DO：领域 router 保持纯净，无 prefix/tags
router = APIRouter()

# ✅ DO：在 api_router.py 中统一聚合配置
api_router.include_router(
    user_router.router,
    prefix="/users",
    tags=["users"]
)

# ✅ DO：端点函数声明 response_model（response_model 仍需在端点加）
@router.post("", response_model=ResponseModel[OrderOut])
async def create_order(
    req: CreateOrderRequest,
    service: OrderServiceDep,  # Annotated 依赖注入
) -> ResponseModel[OrderOut]:
    order = await service.create(req)
    # 使用 mode='json' 安全转录防止 ORJSON 非字符主键崩溃
    clean_data = OrderOut.model_validate(order).model_dump(mode='json')
    return ResponseModel.success(data=clean_data)

# ❌ DON'T
router = APIRouter(prefix="/orders", tags=["orders"])  # ❌ 领域 Router 内禁止配置
async def create_order(req):
    if req.price < 0:  # ❌ 业务逻辑在 Router
        raise ValueError()
    db.add(Order(...))  # ❌ 直接写 SQL
    return {"order": order}  # ❌ 返回原始 Dict
```

#### Service —— 主厨 / 业务大脑
```python
# ✅ DO
from app.utils.masking import mask_phone  # PII 屏蔽库使用

async def create(self, req: CreateOrderRequest) -> OrderOut:
    if req.total_amount <= 0:  # ✅ 业务校验
        raise AppException(OrderError.INVALID_AMOUNT)  # ✅ 必须抛 AppException，禁止 HTTPException
    
    async with self.db.begin():  # ✅ 事务管理（Service 负责 commit/rollback 边界）
        order = await self.repo.create(...)
        await self.repo.record_inventory_change(...)  # ✅ 调用同域 Repo
    
    # ✅ 业务日志且进行敏感信息安全脱敏
    logger.info("order_created", order_id=order.id, phone=mask_phone(req.phone)) 
    return order

# ❌ DON'T
async def create(self, req):
    stmt = select(Order).where(...)  # ❌ Service 写 SQL
    print(f"User {req.phone} buy order")  # ❌ 禁用 print，严禁手机号明文！
    result = await self.db.execute(stmt)  # ❌ 直接操作 Session
    raise HTTPException(status_code=400)  # ❌ Service 层禁止抛 HTTPException
```

#### Repository —— 仓库管理员
```python
# ✅ DO
async def create(self, order: Order) -> Order:
    self.session.add(order)
    await self.session.flush()  # ⚠️ 可选：提前获取 ID，但不 commit（边界由 Service 管控）
    return order

async def get_by_id(self, order_id: UUID) -> Order | None:
    # ✅ 默认过滤软删除
    stmt = select(Order).where(Order.id == order_id, Order.is_deleted == False)
    return await self.session.scalar(stmt)  # 使用 scalar_one_or_none 防止脏多条

# ❌ DON'T
async def create(self, order):
    await self.session.commit()  # ❌ Repository 不负责事务边界（由 Service 管控）
    if order.status not in [OrderStatus.PENDING, OrderStatus.PAID]:
        raise BusinessError()  # ❌ 业务逻辑不属于 Repo
```

#### 跨域调用禁令
```python
# ❌ 违规：orders Service 直接引入 users Service
class OrderService:
    async def create_order(self, req):
        user = await UserService(db).get_user(req.user_id)  # ❌ 严禁！

# ✅ 修复：必须通过 app/services/ 中的 UseCase/Workflow 调度串联组装
class PlaceOrderUseCase:  # 命名规范：跨域编排用 XxxUseCase 或 XxxWorkflow
    async def execute(self, req):
        user = await self.user_service.get_user(req.user_id)
        order = await self.order_service.create(req)
        ...
```

### 第三层：数据库约束层 (Strict Mode)

**原则**：显式优于隐式。在数据库层拦截所有非法状态。

```python
from sqlalchemy import CheckConstraint, Numeric, DateTime, text, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from datetime import datetime

class Order(UUIDModel):
    __tablename__ = "orders"
    
    # ✅ UUID v7 主键（来自 UUIDModel）
    # ❌ 禁止使用自增 Integer 或 UUID v4 作为主键
    
    # ✅ 必填字段：无 Python default，强迫调用方传值（Fail Fast）
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="订单状态"
        # ❌ DON'T: default=OrderStatus.PENDING  ← 破坏 Fail Fast 原则
    )
    
    # ✅ 金额使用 DECIMAL，禁止 Float
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="订单总额 (单位: 元)"
    )
    
    # ✅ JSONB（禁止普通 JSON 类型）+ CheckConstraint 防止存入 List
    metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
        comment="扩展元数据（必须 JSONB）"
    )
    
    # ✅ 时间由数据库生成，且开启时区
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
        comment="创建时间 (UTC)"
    )
    
    # ✅ CheckConstraint 命名规范：ck_{table}_{rule}
    __table_args__ = (
        CheckConstraint(
            f"status IN ('PENDING', 'PAID', 'SHIPPED', 'CANCELLED')",
            name="ck_order_status_valid"
        ),
        CheckConstraint(
            "total_amount > 0",
            name="ck_order_amount_positive"
        ),
        # ✅ JSONB 结构约束：防止存入 List 或 Scalar
        CheckConstraint(
            "metadata IS NULL OR jsonb_typeof(metadata) = 'object'",
            name="ck_order_metadata_is_object"
        ),
        # ✅ 非空字符串约束（防止空格存入）
        # CheckConstraint("length(trim(name)) > 0", name="ck_order_name_not_empty"),
        # ✅ 高频查询复合索引
        Index('ix_order_user_status', 'user_id', 'status'),
    )
```

#### ORM Relationship 策略（No-Relationship 优先）

**原则：默认禁止使用 ORM `relationship` 进行隐式关联。**

- **理由**：避免循环导入、N+1 查询风暴及隐式耦合
- **替代**：仅定义物理 `ForeignKey`，关联查询在 Repository 层通过显式 `join` 或分步查询实现

**例外条款**（满足全部条件时方可使用）：
1. 场景：纯读取聚合查询，或必须使用 eager loading 优化的复杂层级读取
2. 约束：必须在 Repository 层显式指定加载策略（`joinedload` / `selectinload`）
3. 约束：必须在代码注释中说明使用理由及性能评估

#### 级联删除策略（强制）

- **禁止使用 `ondelete="CASCADE"`**
- 核心业务实体必须采用软删除（`is_deleted=True`），严禁物理级联删除
- 所有外键关联必须保留关联数据，以保证历史可追溯性

```python
# ❌ 违规：级联物理删除（数据不可恢复，历史追溯断裂）
user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", ondelete="CASCADE"),
    comment="所属用户"
)

# ✅ 正确：保留外键约束，业务侧软删除
user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id"),  # 无 ondelete
    nullable=False,
    comment="所属用户ID"
)
# 删除时：将记录的 is_deleted 置为 True，而非物理删除父记录
```

### 第四层：代码规范、安全打点与类型工具兼容

#### 1. 强制文件头注释（必须遵守）
**所有非 trivial `.py` 文件第一行必须包含标准文件归属说明。**
```python
"""
File: app/domains/users/schemas.py
Description: 该文件的业务简明扼要中文描述

(可选，复杂模块可提供详尽介绍)

Author: <your-name>
Created: 2026-01-15
"""
```

#### 2. 框架编码红线（完整版）
- **依赖注入红线**：摒弃 `Depends()` 赋默认值，全部转换为 `Annotated` 以规避 Ruff B008 报错
  ```python
  # ❌ 禁止
  async def create_user(service: UserService = Depends(get_user_service)): ...
  # ✅ 必须
  async def create_user(service: UserServiceDep, data: UserCreate): ...
  ```
- **配置读取红线**：读取 `settings` 时，必须直接使用属性访问，禁止 `getattr()`
  ```python
  # ❌ 禁止 getattr(settings, "MY_VAR")
  value = settings.MY_VAR  # ✅ 保留 Pydantic 静态类型推断
  ```
- **仓储实例化红线**：实例化继承自 `BaseRepository` 的类时，必须显式传入 Model 类和 session 关键字参数
  ```python
  # ✅ 必须显式传参
  UserRepository(User, session=db)
  ```
- **静态分析 Hack 铁律**：
  - 注册 `AppException` 全局异常时最后必须用 `# type: ignore[arg-type]`
  - SQLAlchemy 模型动态表名重写必须带上 `@declared_attr.directive`
  - 使用 `X | None` 替代 `Optional[X]`（PEP 604）
  - 路径操作必须使用 `pathlib.Path`

#### 3. Docstring 规范
- 所有非显而易见函数/方法使用 **Google Style**
- 注释只说明"WHY"（为何这样做），不重复翻译代码行为（禁止 #赋值 这种废注释）

---

## 🔄 严格两阶段工作流（强力执行）

### 阶段一：设计期（禁止直接输出代码）

1. **审查需求与澄清边界**
   - 深度分析需求对现有 Router/Service/Repo 的级联影响
   - 如有功能边界模糊、跨模块连锁修改风险或架构冲突，立刻停止并主动提问
2. **分析影响拓扑 (Impact Mapping)**
   ```text
   需求 → 影响的模型 → 影响的 Service → 影响的 Router → 可能的级联失效风险
   ```
3. **输出实施方案**（涉及哪些文件、各层如何设计、兼容旧行为的具体策略）
4. **明确等待"开始实现"指示**，此时绝对不输出代码

### 阶段二：实现期（必须执行完整自检清单）⚠️

**必须且只能当用户明确回复"开始实现"时，才能进入代码编写阶段。**

**在真正产出修改内容前，执行完整自检清单：**

#### A. 增量修改纪律
- [ ] 是否完全兼容了旧有逻辑？（除非明确要求删除，严禁精简既有功能）
- [ ] 是否遵守 Minimal Diff 原则？（拒绝任何与当前任务无关的重构/重命名/格式化）
- [ ] 失败路径是否显式处理且未吞咽异常？（禁止空 catch 块）

#### B. 架构与分层
- [ ] 所有函数是否为 `async def`？
- [ ] Router 是否只调用 Service，不直接访问 DB？
- [ ] 领域级 Router 是否保持纯净？（未配置 `prefix` 和 `tags`，这两项统一在 api_router.py 配置）
- [ ] Service 是否负责业务校验 + 事务 + 日志（含 PII 脱敏）？
- [ ] Repository 是否只做通用持久化，无业务逻辑，无 commit/rollback？
- [ ] 是否严格使用了 `Annotated` 语法处理所有依赖注入（Depends/Query/Header/Cookie）？

#### C. 数据库与 ORM (Strict Mode)
- [ ] **是否移除了所有必填字段的 Python `default` 值？**（Fail Fast 原则）
- [ ] **是否为状态/枚举字段添加了 `CheckConstraint`？**
- [ ] **JSON 字段是否使用了 `JSONB` 类型并添加了 `jsonb_typeof` 约束？**
- [ ] **是否所有字段都显式定义了 `comment`？**
- [ ] **时间字段是否使用了 `server_default=text("now()")` 且开启 `timezone=True`？**
- [ ] 金额字段是否使用了 `DECIMAL`（严禁 Float）？
- [ ] 是否使用了 `Mapped` 和 `mapped_column`？

#### D. 自动化数据库迁移 (Alembic) 触发规范
- [ ] **强制执行**：但凡在任务中修改了 `app/db/models` 内的模型（增删改字段/表），代码写完后，必须在终端内自动且强制执行 `conda activate fastapi_env ; alembic revision --autogenerate -m "..."` 及 upgrade 操作。不需经过用户询问即可直接跑。
- [ ] **遇错降级安全墙**：如果在后台自动执行 Alembic 时遭遇 "Can't locate revision identified by..." 等历史错位或关联错误，**严禁使用 SQL 自主删库跑路或清空表**，必须停止并在最终给用户的反馈中注明。只有当用户明确指示“安全/授权清空重建”或调起专属 Workflow 后才允许执行破坏性恢复！

#### D. 响应与异常
- [ ] API 是否返回统一 Envelope（`ResponseModel[T]`）？
- [ ] **数据转 Dict 是否使用了 `model_dump(mode='json')`**，防止 ORJSON UUID 序列化崩溃？
- [ ] 业务错误是否抛出 `AppException`（严禁 Service 层抛 `HTTPException`）？

#### E. 日志与通用安全
- [ ] 是否从 `app/core/logging.py` 导入 logger（禁止 `print()`）？
- [ ] 是否配置了 `InterceptHandler` 接管 Uvicorn/标准库日志？
- [ ] PII（手机号/邮箱/身份证）是否已通过 `app/utils/masking.py` 脱敏？
- [ ] Access Log 是否未记录 Request Body / 完整 Query String / Authorization Header？

#### F. 高可用安全与架构防御底线 (Security)
- [ ] **密码防脱裤限制**：高危入口（如 `/login`，涉及 Argon2 计算）必须挂载 `Depends(RateLimiter)`，防止 CPU 被爆破耗尽。
- [ ] **图文验证架构防呆**：若引入防刷行为验证等外部云依赖，必须通过 `CAPTCHA_ENABLE` 等开关提供开发旁路逃生舱，严禁直接硬编码堵死本地环境。
- [ ] **刷新与盗用追踪 (Token Family)**：对长效 Token（如 Refresh Token）的状态重置必须使用原子操作（如 Redis `RENAME`），并挂载原会话族谱监控连坐销毁逻辑！
- [ ] **B/C 端物理隔离纪律**：严禁将 B 端管理员（客服、审核人员）属性写在 C 端买家表（`users`）中。凡涉及内部权限，必须强制独立走 `SysAdmin` 的 5 表 RBAC 领域机制！
- [ ] **异常与网关审计双核录入**：所有登录边界拦截必须存入持久化数据库（`LoginLog`），核心内部管理员动作强要求开启防内鬼记录，且动作参数必须原封用 JSONB （`AuditLog`）留存底案。
- [ ] **JWT 双端 `aud` 隔离**：B 端 Token 必须在 Payload 中注入 `aud: "backend"`，C 端 Token 注入 `aud: "frontend"`。`deps.py` 中的 `get_current_user` 和 `get_current_admin` 必须分别校验 `aud` 字段，拒绝跨端访问。
- [ ] **AuditLogMiddleware 全量拦截规范**：`AuditLogMiddleware` 必须拦截 `/admin/` 路径下的所有请求（含 GET），采用旁路独立 Session 提交，写入失败不得阻塞主请求（Fail-Open）。请求体中的 password/token 等敏感字段必须自动脱敏为 `***` 后再落库。
- [ ] **超级管理员种子脚本 (`seed_admin.py`)**：每个项目必须在 `scripts/seed_admin.py` 中提供幂等的超级管理员初始化脚本。该脚本需创建基础权限树、SUPER_ADMIN 角色并完成绑定。支持通过环境变量 `SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD` 自定义账密。
- [ ] **购物车 X-Device-Id 双轨鉴权**：小程序购物车等支持游客态的接口，必须使用 OptionalCurrentUser，不得强制登录验证。兼容身份优先级：user_id (Token) > nonymous_id (X-Device-Id)。
- [ ] **订单地址快照铁律**：订单表中禁止保存 ddress_id 外键，必须调用 AddressService.get_snapshot() 将地址全量字段拷贝入订单表的 JSONB 字段。这确保用户修改/删除地址不影响历史订单。

#### G. 多渠道认证与社交绑定安全 (Auth Multi-Channel)
- [ ] **手机号锚点原则**：手机号是唯一身份标识，所有登录链路最终必须绑定手机号。密码字段必须可选 (`nullable=True`)，支持无密码注册。
- [ ] **短信验证码安全链**：60秒发送冷却锁 + 5次错误自动销毁验证码 + 验证通过后立即删除 + `sms_logs` 审计表永久留存。
- [ ] **微信工具旁路开关**：AppID/AppSecret 为空时必须返回固定测试数据，严禁不配置就崩溃。
- [ ] **社交绑定 platform 白名单**：`platform` 字段只允许 `wechat_mini`, `wechat_mp`, `wechat_web`，必须在 Service 层或 Schema 层校验。
- [ ] **解绑安全检查**：解绑前必须检查用户是否至少保留一种登录方式（密码或其他社交绑定），否则拒绝解绑。
- [ ] **临时凭证安全**：扫码登录 temp_token 必须存 Redis (5分钟 TTL + 一次性消费)，禁止存数据库或内存。
- [ ] **软删除手机号不可复活**：已注销用户的手机号不得被重新注册，必须返回"该手机号关联的账号已被注销"。

---

## 🛑 常见业务与基础体系违规

*(这里列举的违纪现象是 AI 产出中最为高频翻车的场景)*

### 违规 #1：领域 Router 内配置 prefix 和 tags（最新红线！）
```python
# ❌ 违规（领域内 router.py 禁止配置 prefix 和 tags）
router = APIRouter(prefix="/orders", tags=["orders"])

# ✅ 修复：领域 router.py 内保持纯净
router = APIRouter()

# ✅ 在 app/api_router.py 中统一聚合
api_router.include_router(order_router.router, prefix="/orders", tags=["orders"])
```

### 规范 #0：领域 Router 的 B/C 端双轨命名约定（强制）

凡需要同时为 C端用户与 B端管理员提供接口的领域，必须在领域的 `router.py` 内定义 **2 个 APIRouter 实例** 并按以下规范命名：

```python
# app/domains/products/router.py
from fastapi import APIRouter

# C端（买家）路由器 —— 命名规范：{领域名}_router
products_router = APIRouter()

# B端（管理员）路由器 —— 命名规范：{领域名}_admin
products_admin = APIRouter()
```

```python
# app/api_router.py 中的聚合规范：
from app.domains.products.router import products_router, products_admin

api_router.include_router(products_router, prefix="/products",       tags=["C端商品"])
api_router.include_router(products_admin,  prefix="/admin/products", tags=["B端商品管理"])
```

| 变量名 | 接口前缀示例 | 访问者 |
|--------|------------|--------|
| `{领域}_router` | `/api/v1/{领域}/` | C端用户（买家） |
| `{领域}_admin` | `/api/v1/admin/{领域}/` | B端管理员（需 `aud=backend` Token） |

> ⚠️ **严禁**全部命名为 `public_router / admin_router`，聚合时多领域必然撞名，被迫写难以维护的 `as` 别名。

### 违规 #2：OpenAPI 文档裸奔 (影响前端沟通定型)
```python
# ❌ 违规（没用 response_model，前端无法推导返回值）
@router.post("/auth")
async def login(req: LoginReq, service: AuthServiceDep): ...

# ✅ 修复：必须配置 response_model
@router.post(
    "/auth",
    summary="用户登录并签发票据",
    response_model=ResponseModel[TokenOut]
)
async def login(...): ...
```

### 违规 #3：违背 Fail Fast — 使用默认值代替强制传值
```python
# ❌ 违规（Fail Fast 原则被破坏，用户忘了发 status 却不会报错）
class User(UUIDModel):
    status: Mapped[str] = mapped_column(default="active")  

# ✅ 修复：无默认值 + CheckConstraint
class User(UUIDModel):
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="账号状态")
    __table_args__ = (CheckConstraint("status IN ('active', 'banned')", name="ck_user_status_valid"),)
```

### 违规 #4：在 Router 中写业务逻辑和跨层操作
```python
# ❌ 违规
@router.post("/orders")
async def create_order(req: CreateOrderRequest, db: AsyncSession) -> dict:
    if req.total_amount < 0:  # ❌ 业务逻辑在 Router
        raise HTTPException(status_code=400)
    order = Order(**req.model_dump())
    db.add(order)
    await db.commit()  # ❌ 事务管理跨界
    return {"order": order}

# ✅ 修复：领班只管端盘子，把一切业务推入 Service！
```

### 违规 #5：ORJSON 序列化猝死 (因 UUID 未拦截引发)
```python
# ❌ 违规（ORJSON 收到含未安全转换对象的 Python 字典当场报 500）
return ResponseModel.success(data={"id": uuid_obj, "count": 10})

# ✅ 修复：必须让 Pydantic 做前置处理网兜
data_schema = UserOut.model_validate(orm_obj)
safe_dict = data_schema.model_dump(mode='json')  # ✅
return ResponseModel.success(data=safe_dict)
```

### 违规 #6：JSON 字段使用普通 JSON 类型（缺少 JSONB + 约束）
```python
# ❌ 违规（普通 JSON 类型，可以存 List 和 Scalar，无法防御）
config: Mapped[dict] = mapped_column(JSON, nullable=True, comment="配置")

# ✅ 修复：必须用 JSONB + JSONb 结构约束
config: Mapped[dict] = mapped_column(JSONB, nullable=True, comment="配置")
__table_args__ = (
    CheckConstraint("config IS NULL OR jsonb_typeof(config) = 'object'", name="ck_xxx_config_is_object"),
)
```

### 违规 #7：Service 层抛出 HTTPException
```python
# ❌ 违规（Service 层感知了 HTTP 层细节，违反分层）
class UserService:
    async def create(self, req):
        raise HTTPException(status_code=409, detail="手机号已存在")

# ✅ 修复：Service 只抛 AppException，由全局异常处理器转换
class UserService:
    async def create(self, req):
        raise AppException(UserError.PHONE_EXIST)
```

### 违规 #8：使用同步 `requests` 库或 `time.sleep()`
```python
# ❌ 违规（在 async 环境中阻塞事件循环）
import requests
response = requests.get("https://api.example.com")
time.sleep(5)

# ✅ 修复
import httpx
async with httpx.AsyncClient() as client:
    response = await client.get("https://api.example.com")
await asyncio.sleep(5)

# ⚠️ 特殊：密码 Hash 等 CPU 密集操作必须包裹 run_in_threadpool
from fastapi.concurrency import run_in_threadpool
hashed = await run_in_threadpool(bcrypt.hash, password)
```

---

## 🔀 中间件规范（Middleware）

- **唯一定义位置**：仅在 `app/core/middleware.py` 定义
- **统一注册方式**：在 `main.py` 通过 `register_middlewares(app)` 注册，**禁止**在 Router / Domain 内注册中间件
- **禁止中间件包裹响应体**：统一响应由 Router + 全局异常处理器完成，在中间件中读取并重写 response body 会破坏 FastAPI 的流式响应性能

**LoggingMiddleware 四项必须**：
1. 生成 UUID v7 `request_id`
2. 记录 access log（遵守安全铁律：仅记录 Method/Path/Status/Duration/RequestID）
3. 使用 `logger.contextualize(request_id=request_id)` 注入 Loguru 上下文
4. 回传响应头 `X-Request-ID: <uuid7>`

**允许不使用统一 Envelope 的例外场景**（需在 Router 注释说明原因）：
- `/health` 等健康检查端点
- 流式响应（SSE / 文件下载 / WebSocket）
- 明确要求透明透传的代理接口

---

## ⚙️ 日志规范速查

### 分层日志职责

| 层级 | 日志职责 |
|------|----------|
| **Middleware（必须）** | 记录 access log：method/path/status/duration/request_id（禁止记录 Body/Query String/Auth Header） |
| **Router（可选）** | 记录关键接口入口，不包含业务细节 |
| **Service/UseCase/Workflow（必须）** | 记录业务开始/结束、关键判断点、领域异常（含 PII 脱敏） |
| **Repository（仅 DEBUG）** | 只在调试排查时记录 DB 细节，生产禁止大量 SQL 明细输出 |

### 日志级别规范

| 级别 | 适用场景 |
|------|----------|
| DEBUG | 调试细节、SQL 语句、分支路径追踪 |
| INFO | 关键业务步骤、正常流程（如 `order_created`） |
| WARNING | 可恢复的业务异常、预期外但未失败的情况 |
| ERROR | 业务失败、系统异常（必须带堆栈） |
| CRITICAL | 系统不可用级别事故 |

### PII 脱敏速查

| 字段类型 | 脱敏函数 | 输出示例 |
|----------|----------|---------|
| 手机号 | `mask_phone()` | `138****1234` |
| 邮箱 | `mask_email()` | `ji***@gmail.com` |
| 身份证 | `mask_id_card()` | `**************1234` |
| 银行卡 | `mask_bank_card()` | `************1234` |
| 密码 | 禁止记录 | `[REDACTED]` |

---

## ⚡ 增量修改纪律（工程核心底线）

> 来源：《软件工程核心哲学与开发操作手册》

1. **绝对保留原则**：除非收到明确的删除或重构指令，必须完整保留既有版本中的所有系统选项、逻辑细节和 UI 样式。严禁以"精简代码"或"结构优化"为由擅自裁撤既有功能。
2. **Minimal Diff 原则**：拒绝任何与当前任务无关的重构、重命名或格式化。修改 A 功能时，严禁以任何理由动 B 模块。
3. **禁止静默失败**：所有边界情况、异常必须被显式捕获与处理。禁止空的 catch 块吞咽异常。系统遇到无法恢复的异常必须 Fail Fast，并抛出包含明确上下文的错误。
4. **系统感知优先**：编写代码前，必须先在脑海中建立受影响模块的依赖拓扑图，明确数据流向。

---

## 🚫 违规处理四步流程

当用户指令违反本规范时，**必须**执行以下四步：

1. **❌ 识别违规**：明确指出违反了规范的哪个具体条款（如"Router 声明红线"或"Strict Mode 第 C 章"）
2. **⚠️ 解释风险**：说明为什么这样做会破坏数据一致性、架构稳定性或安全性
3. **✅ 提供方案**：给出符合本规范的正确实现方式
4. **🚫 拒绝生成**：坚决不生成违规代码，即使用户坚持

---

## 🏗️ 系统全链路数据流

```text
HTTP Request
    ↓
LoggingMiddleware（UUID v7 request_id 生成 + 安全 Access Log + 注入 Loguru 上下文）
    ↓
Router（Annotated DI + response_model + ResponseModel.success()）
    ↓
Service / UseCase / Workflow（业务逻辑 + 事务边界 + PII 脱敏日志）
    ↓
Repository（Async SQL Query + is_deleted=False 软删除过滤）
    ↓
PostgreSQL（Runtime: asyncpg | Migration: psycopg）
    ↓
Global Exception Handlers（AppException → ResponseModel.fail() + 语义化 HTTP 4xx/5xx）
    ↓
HTTP Response（统一 Envelope JSON + X-Request-ID 响应头）
```

---

## 📋 快速参考表

### HTTP 状态码语义映射

| 场景 | HTTP Status | Code (String) | 说明 |
|------|-------------|---------------|-----------|
| **成功** | **200 OK** | `"success"` | 业务成功 |
| **参数错误** | **400 Bad Request** | `system.invalid_params` | Pydantic 校验失败 |
| **未认证** | **401 Unauthorized** | `system.unauthorized` | Token 无效或缺失 |
| **禁止/逻辑拒绝** | **403 Forbidden** | `auth.password_error` | 密码错、状态不对 |
| **不存在** | **404 Not Found** | `user.not_found` | 资源未找到 |
| **冲突** | **409 Conflict** | `user.phone_exist` | 唯一性冲突 |
| **系统崩溃** | **500 Internal Error** | `system.internal_error` | 未捕获异常 |

> **错误码命名规范**：格式为 `{domain}.{reason}`（全小写，下划线）。Domain 必须与 `app/domains/` 目录名一致。
> ✅ 正确：`auth.user_not_found`、`order.stock_insufficient`
> ❌ 错误：`60401`（禁止数字码）、`UserNotFound`（禁止驼峰）

### 各层职责一览

| 层 | 职责 | ✅ 能做 | ❌ 禁止 |
|---|---|---|---|
| **Router** | HTTP 接口 | 声明 response_model、序列化模型、包裹成功响应 | 配置 prefix/tags（在 api_router.py）、写业务逻辑、SQL、返回原始 Dict |
| **Service** | 业务编排 | 业务校验、打 PII 日志、协调 Repository、管控事务边界（commit/rollback）| 越权调用其他领域 Service、写 SQL、抛 HTTPException |
| **Repository** | 数据访问 | 查询构建、`scalar_one_or_none`、flush、默认过滤软删除 | 业务 if/else、权限判断、commit/rollback、业务日志 |
| **Models** | 数据结构 | 集中管理、UUIDv7 主键、CheckConstraint 约束、字段 comment | 省略 comment、生成假默认值、使用 Float/JSON 类型 |

### 命名规范速查

| 位置 | 命名规范 | 示例 |
|------|----------|------|
| `app/domains/<domain>/service.py` | `XxxService` | `UserService` |
| `app/services/<usecase>/` | `XxxUseCase` | `PlaceOrderUseCase` |
| `app/services/<workflow>/` | `XxxWorkflow` | `CheckoutWorkflow` |
| Pydantic 输入 | `XxxCreate` / `XxxUpdate` | `UserCreate` |
| Pydantic 输出 | `XxxRead` / `XxxProfile` | `UserRead` |
| Pydantic 内部 | `XxxInDB` | `UserInDB` |

> **禁止**在 `app/services/` 中出现 `XxxService` 命名（那是领域内 Service 的命名）

### 数据类型映射速查

| 业务 | Python | SQL Type | Default 策略 |
|:---|:---|:---|:---|
| **金额** | `Decimal` | `DECIMAL(15, 2)` | 无默认值（严禁 Float） |
| **比率** | `Decimal` | `DECIMAL(15, 4)` | 无默认值（严禁 Float） |
| **文本（必填）** | `str` | `String(N)` | 无默认值（禁止 default） |
| **文本（选填）** | `str \| None` | `String(N)` | `nullable=True` |
| **JSON** | `dict` | `JSONB` | 无默认值（必须 JSONB + CheckConstraint） |
| **时间** | `datetime` | `DateTime(timezone=True)` | `server_default=text("now()")` |
| **枚举/状态** | `str` | `String(N)` | 无默认值 + CheckConstraint |

### 必须文件清单

| 文件 | 必须包含 |
|------|----------|
| `app/core/response.py` | `ResponseModel[T]`、`success()` / `fail()` + **JSON mode dump** |
| `app/core/error_code.py` | `BaseErrorCode` 枚举基类 |
| `app/core/exceptions.py` | `AppException` + handler 注册（注册处用 `# type: ignore[arg-type]`） |
| `app/db/models/base.py` | `UUIDModel`（含 uuid7 主键、is_deleted、时区时间戳） |
| `app/core/logging.py` | Loguru + JSON 序列化 + **InterceptHandler 标准库劫持** |
| `app/utils/masking.py` | PII 脱敏工具函数 |
| `alembic/env.py` | `postgresql+psycopg`（Psycopg 3）同步驱动迁移配置 |
| `app/api_router.py` | 统一聚合所有领域 Router 并配置 prefix + tags |

---

## 🧱 基建骨架代码（已验证，禁止重新发明）

当需要生成以下基础设施代码时，**必须严格使用本节已验证代码片段**，禁止自行重新发明。

### 骨架 1：日志配置 (`app/core/logging.py`)

**关键点**：Loguru 配置、JSON 序列化、**InterceptHandler（标准库劫持）**。

```python
import logging
import sys
from types import FrameType
from typing import cast, Any
from pathlib import Path

from loguru import logger
from app.core.config import settings

class InterceptHandler(logging.Handler):
    """
    将 Python 标准库 logging 拦截并转发到 Loguru 的 Handler。
    用于接管 Uvicorn / FastAPI 的内部日志。
    """
    def emit(self, record: logging.LogRecord) -> None:
        # 获取对应的 Loguru 日志级别
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 查找调用者的栈帧，以确保日志行号正确
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            if frame.f_back:
                frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def format_record(record: dict[str, Any]) -> str:
    """
    自定义日志格式函数。
    如果在 context 中存在 request_id，则将其包含在日志中。
    """
    format_string = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    if record["extra"].get("request_id"):
        format_string += " | <magenta>req_id={extra[request_id]}</magenta>"

    format_string += "\n{exception}"
    return format_string

def setup_logging() -> None:
    """
    初始化日志配置。
    应在 main.py 启动时调用。
    """
    # 1. 拦截标准库日志 (Uvicorn / FastAPI)
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(settings.LOG_LEVEL)

    # 移除 Uvicorn 默认的 handlers，避免重复打印
    for name in logging.root.manager.loggerDict.keys():
        if name.startswith("uvicorn.") or name.startswith("fastapi."):
            logging.getLogger(name).handlers = []
            logging.getLogger(name).propagate = True

    # 2. 配置 Loguru Sink
    logger.remove()

    # 通用配置
    base_config: dict[str, Any] = {
        "level": settings.LOG_LEVEL,
        "enqueue": True,  # 异步写入，生产环境必须
        "backtrace": True,
        "diagnose": settings.LOG_DIAGNOSE,
    }

    # Sink 1: 控制台
    console_config = base_config.copy()
    if settings.LOG_JSON_FORMAT:
        console_config["serialize"] = True
    else:
        console_config["format"] = format_record
        console_config["colorize"] = True
    logger.add(sys.stdout, **console_config)

    # Sink 2: 文件 (可选)
    if settings.LOG_FILE_ENABLED:
        log_dir = Path(settings.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "app_{time:YYYY-MM-DD_HH}.log"

        file_config = base_config.copy()
        file_config.update({
            "rotation": settings.LOG_ROTATION,
            "retention": settings.LOG_RETENTION,
            "compression": settings.LOG_COMPRESSION,
        })
        if settings.LOG_JSON_FORMAT:
            file_config["serialize"] = True
        else:
            file_config["format"] = format_record
        logger.add(str(log_path), **file_config)
```

---

### 骨架 2：统一响应封装 (`app/core/response.py`)

**关键点**：`model_dump(mode='json')` 确保 ORJSON 兼容性，统一 Envelope。

```python
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

class ResponseBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str = Field(default="success", description="业务状态码")
    message: str = Field(default="Success", description="响应消息")
    request_id: str | None = Field(default=None, description="请求追踪ID")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="响应生成时间",
    )

class ResponseModel(ResponseBase, Generic[T]):
    data: T | None = Field(default=None, description="业务数据")

    @classmethod
    def success(
        cls,
        data: T | None = None,
        message: str = "Success",
        request_id: str | None = None,
    ) -> "ResponseModel[T]":
        # DEFENSIVE CODING: Force convert Pydantic models to JSON-safe dicts
        # This prevents ORJSON from crashing on non-string keys or complex types
        if hasattr(data, "model_dump"):
            data = data.model_dump(mode="json")
        return cls(code="success", message=message, data=data, request_id=request_id)

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        data: Any = None,
        request_id: str | None = None,
    ) -> "ResponseModel[Any]":
        return cls(code=code, message=message, data=data, request_id=request_id)
```

---

### 骨架 3：ORM 基类 (`app/db/models/base.py`)

**关键点**：UUID v7 主键、PostgreSQL Strict Mode（时间/时区/注释/ServerDefault）。

```python
import uuid
from datetime import datetime
from uuid6 import uuid7
from sqlalchemy import text, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

class Base(DeclarativeBase):
    """
    SQLAlchemy 声明式基类。
    所有数据模型（Model）必须继承此类（或其子类）。
    """
    pass

class UUIDModel(Base):
    """
    [推荐标准] UUID v7 主键模型基类 (Strict Mode)。

    适用于大多数标准业务实体表。自动获得：
    - id: UUID v7 主键
    - is_deleted: 软删除标记
    - created_at: 创建时间 (DB Server Time)
    - updated_at: 更新时间 (DB Server Time)
    """
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid7,
        comment="UUID v7 主键"
    )

    is_deleted: Mapped[bool] = mapped_column(
        default=False,
        index=True,
        comment="软删除标记"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
        comment='创建时间 (UTC)'
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
        comment='更新时间 (UTC)'
    )
```

---

### 骨架 4：Alembic 迁移配置关键片段 (`alembic/env.py`)

**关键点**：使用 `psycopg`（v3）同步驱动，禁止 psycopg2。

```python
# ... alembic/env.py 内 ...

from app.core.config import settings

# 强制：迁移使用同步 psycopg 驱动（Psycopg 3）
# 将 postgresql+asyncpg 替换为 postgresql+psycopg
try:
    async_uri = str(settings.SQLALCHEMY_DATABASE_URI)
    sync_uri = async_uri.replace("postgresql+asyncpg", "postgresql+psycopg")
except Exception:
    # 回退构造
    sync_uri = (
        f"postgresql+psycopg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )

# ... 其余迁移配置 ...
```

---

### 骨架 5：标准文件头模板（所有 `.py` 文件）

**关键点**：所有非 trivial `.py` 文件第一行必须包含，禁止省略。

```python
"""
File: <path/to/file.py>
Description: <该文件的业务简明扼要中文描述>

<详细说明（可选，复杂模块可提供）>

Author: <your-name>
Created: <YYYY-MM-DD>
"""
```

---

## 💬 获取帮助指南

在任何开发任务中，使用以下格式告诉我需求：
1. **你要做什么**（业务述求核心点）
2. **现状是什么**（附上核心数据表路径和文件情况）

我将用完全符合此规范框架的逻辑给你兜底，确保工程架构不在长时间更迭与散弹式代码变更中被锈蚀。

> **本文件是项目唯一工程规范（Self-Contained Source of Truth）。**
> **所有骨架代码已内嵌于本文件「基建骨架代码」章节，零外部依赖，新项目直接使用本文件即可。**


---

## 🆕 已落地业务领域扩展备忘录 (2026-04 更新)

以下是基于本标准规范新增实现的领域模块，作为对"已实现的核心基础设施模块"章节的扩展补充：

| 模块 | 文件/领域 | 职责 |
|------|-----------|------|
| 媒体素材 | domains/media/ | Pillow AOT 图片派生 (1080px _large / 400px _thumb) + LocalStorageProvider |
| 商品体系 | domains/products/ | 5级价格引擎 + 3级分佣 + SPU/SKU + 分类树 + UPSERT 浏览足迹 |
| 购物车 | domains/carts/ | OptionalCurrentUser + X-Device-Id 双轨身份 + 游客合并算法（叠加/过户） |
| 收货地址 | domains/addresses/ | 行政编码双存 + is_default 互斥引擎 + AddressSnapshot 快照预留 |

### 新增工程规范（重要！）

#### 规范 E1: OptionalCurrentUser 双轨鉴权（购物车/游客接口专用）

对于小程序等支持游客态的接口，必须使用 deps.py 中的 OptionalCurrentUser 而不是 CurrentUser，不得强制拦截登录：

`python
# app/api/deps.py 中已实现
async def get_optional_current_user(...) -> User | None:
    # Token 缺失/失效时静默返回 None，不抛 401
    ...

OptionalCurrentUser = Annotated[User | None, Depends(get_optional_current_user)]
`

接口中的身份优先级：user_id (Token) > nonymous_id (X-Device-Id Header)

#### 规范 E2: 订单地址快照铁律（绝不存外键）

订单下单时，禁止在订单表中保存 ddress_id 外键引用。   
必须调用 AddressService.get_snapshot(user_id, address_id) 获取 AddressSnapshot 结构，  
将地址全量数据序列化后存入订单表的 JSONB 字段。  
这确保用户修改/删除收货地址不影响任何历史订单的显示。

#### 规范 E3: 购物车绝不落地价格

购物车表（cart_items）中绝对不存储任何价格字段。  
每次 GET /carts/my 时，必须逐条通过 ProductService 的 5 级价格引擎实时计算当前展示价。  
这杜绝了"历史价格越权"的价格雪崩场景。
