# CONCERNS.md — 已知问题与风险

## 🔴 高优先级

### C-001: auth/schemas.py 跨域导入 users/schemas.py 常量
- **位置**: `app/domains/auth/schemas.py` 第 19-24 行
- **问题**: `auth` 领域直接导入了 `users` 领域的校验常量（`PHONE_CODE_PATTERN`, `MOBILE_PATTERN` 等），违反了 `.importlinter` 中定义的"领域间禁止互相导入"约束（`no_cross_domain_imports` 合约）。
- **影响**: 若启用 import-linter CI 检查，此处会报错。
- **建议**: 将共享的校验常量（正则模式 + 错误消息）提取到 `app/core/validators.py` 或 `app/core/constants.py` 中，让两个领域都从 core 层导入。

### C-002: tests/ 目录缺失
- **位置**: 项目根目录
- **问题**: `pyproject.toml` 配置了 `testpaths = ["tests"]`，但 `tests/` 目录实际不存在。
- **影响**: `pytest` 运行时会因找不到测试目录而报 warning / 无测试执行。
- **建议**: 在首个功能稳定后，创建 `tests/conftest.py` 和基础测试用例。

### C-003: repository.py 文件头注释未同步更新
- **位置**: `app/domains/users/repository.py` 第 7 行
- **问题**: 注释仍写着 `get_by_phone_number`，但方法已重命名为 `get_by_mobile`。
- **影响**: 纯文档层面的不一致，不影响运行，但可能误导后续维护者。
- **建议**: 更新注释行。

## 🟡 中优先级

### C-004: UserBase.full_name 字段在 Model 中不存在
- **位置**: `app/domains/users/schemas.py` 第 65-67 行
- **问题**: `UserBase` Schema 声明了 `full_name` 字段，但 `app/db/models/user.py` 的 `User` 模型中没有对应的 `full_name` 列。模型中只有 `nickname`。
- **影响**: 如果前端传入 `full_name`，在通过 `model_dump()` → `user.update()` 赋值时会被 `hasattr` 过滤掉，数据静默丢失。
- **建议**: 统一为 `nickname`（或在 Model 中增加 `full_name` 列），确保 Schema 和 Model 字段对齐。

### C-005: auth service 中 login 方法的 LoginLog TODO 未实现
- **位置**: `app/domains/auth/service.py` 第 139 行
- **问题**: `# TODO: 待 LoginLog 模型实现后，改为 ORM 持久化`。当前仅通过 `logger.info()` 记录登录事件，没有落库。
- **影响**: 无法做登录审计查询（如"最近 7 天的异常 IP 登录"），只能翻日志文件。
- **建议**: 创建 `LoginLog` 模型 + Repository，在此处插入记录。

### C-006: import-linter 配置引用了不存在的领域
- **位置**: `.importlinter` 第 11-16 行
- **问题**: `domains_independent` 合约列出了 `app.domains.orders`, `app.domains.products`, `app.domains.inventory`，但这些领域目录尚不存在。
- **影响**: import-linter 运行时可能因模块不存在而报 warning 或跳过。
- **建议**: 移除尚不存在的模块，待实际创建时再添加。

### C-007: no_orm_in_service 约束与实际代码冲突
- **位置**: `.importlinter` 第 48-54 行 vs `app/domains/auth/service.py` 第 30 行
- **问题**: 合约禁止 `app.domains.*.service` 导入 `app.db.models`，但 `AuthService` 直接导入了 `from app.db.models.user import User` 来实例化模型对象。`UserService` 同理。
- **影响**: import-linter 运行时会报违约。
- **建议**: 若保留此约束，需重构为在 Repository 层提供 `create()` 工厂方法；若约束过严，可考虑放宽或增加豁免。

## 🟢 低优先级

### C-008: Docker 配置未验证
- **位置**: `Dockerfile`, `docker-compose.yml`
- **问题**: 容器化配置文件存在但未验证是否能成功构建和运行。
- **建议**: 在部署前执行 `docker-compose up --build` 验证。

### C-009: hatchling 构建配置缺失
- **位置**: `pyproject.toml` → `[build-system]`
- **问题**: 使用 `hatchling` 作为构建后端，但未指定 `[tool.hatch.build.targets.wheel]` 的 `packages` 字段。当 `uv run` 尝试创建 editable 安装时会报 `Unable to determine which files to ship inside the wheel`。
- **影响**: `uv run python script.py` 命令失败，需回退到直接 `python script.py`。
- **建议**: 在 `pyproject.toml` 中添加：
  ```toml
  [tool.hatch.build.targets.wheel]
  packages = ["app"]
  ```
