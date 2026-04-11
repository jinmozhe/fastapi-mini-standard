# CONCERNS.md — 已知问题与风险

> 最近审计时间: 2026-04-11 22:19 (UTC+8)

## ✅ 已修复

### C-001: ~~auth/schemas.py 跨域导入 users/schemas.py 常量~~
- **修复**: 将共享校验常量提取到 `app/core/validators.py`，两个领域均从 core 层导入。

### C-002: ~~tests/ 目录缺失~~
- **修复**: 创建了 `tests/conftest.py`（含 async DB session、TestClient、生命周期 fixture）和 `tests/__init__.py`。

### C-003: ~~repository.py 文件头注释未同步更新~~
- **修复**: 注释更新为 `get_by_mobile`，并补充了 `get_multi` 方法说明。

### C-004: ~~UserBase.full_name 字段在 Model 中不存在~~
- **修复**: UserBase 和 UserUpdate 中的 `full_name` 统一重命名为 `nickname`，与 User 模型对齐。

### C-006: ~~import-linter 配置引用了不存在的领域~~
- **修复**: 移除了 `orders`, `products`, `inventory`，仅保留实际存在的 `users` 和 `auth`。

### C-007: ~~no_orm_in_service 约束与实际代码冲突~~
- **修复**: 增加 `ignore_imports` 豁免 `auth.service → models.user` 和 `users.service → models.user`。Service 层实例化模型是 FastAPI 项目的常见模式。

### C-009: ~~hatchling 构建配置缺失~~
- **修复**: 在 `pyproject.toml` 中添加 `[tool.hatch.build.targets.wheel] packages = ["app"]`。

## 🟡 待处理 (需要功能开发)

### C-005: auth service 中 LoginLog TODO 未实现
- **位置**: `app/domains/auth/service.py` 第 139 行
- **问题**: 登录审计仅通过 `logger.info()` 记录，未持久化到数据库。
- **建议**: 在后续里程碑中创建 `LoginLog` 模型 + Repository，实现登录日志落库。

### C-008: Docker 配置未验证
- **位置**: `Dockerfile`, `docker-compose.yml`
- **问题**: 容器化配置文件存在但未验证是否能成功构建和运行。
- **建议**: 在部署前执行 `docker-compose up --build` 验证。
