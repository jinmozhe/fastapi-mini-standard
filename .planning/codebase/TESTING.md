# TESTING.md — 测试策略

## 框架与配置
- **测试框架**: Pytest ≥8.2.0
- **异步支持**: pytest-asyncio ≥0.23.0（`asyncio_mode=auto`）
- **HTTP 客户端**: httpx ≥0.27.0（用于 API 端到端测试）
- **配置位置**: `pyproject.toml` → `[tool.pytest.ini_options]`
- **测试目录**: `tests/`（`testpaths = ["tests"]`）
- **Fixture 作用域**: `asyncio_default_fixture_loop_scope = "session"`

## 当前测试状态
> ⚠️ **`tests/` 目录当前不存在**。项目处于基础架构搭建阶段，尚未编写业务测试。

## 建议的测试结构
```
tests/
├── conftest.py              # 全局 Fixture（TestClient, 测试 DB Session, Mock Redis）
├── test_auth/
│   ├── test_register.py     # 注册流程（默认/自定义 phone_code, 唯一性冲突）
│   ├── test_login.py        # 登录（正常, 错误密码, 账号锁定）
│   └── test_refresh.py      # Token 刷新（正常, 过期, 重放）
└── test_users/
    ├── test_get_user.py     # 获取用户（正常, 软删除, 未授权）
    └── test_update_user.py  # 更新用户（唯一性冲突, 密码修改）
```

## 关键测试场景
1. **phone_code 默认值注入**: 不传/传空 → 自动补全为 `+86`
2. **复合唯一约束**: 相同 `phone_code` + `mobile` 重复注册 → 409
3. **Token Rotation**: 使用 Refresh Token 后旧 Token 失效
4. **软删除隔离**: 软删除用户不应出现在查询结果中
5. **字段校验边界**: `mobile` 非纯数字、长度 <5 或 >15 → 400

## 代码质量保障
- **import-linter**: `.importlinter` 配置了 5 条架构约束
- **Mypy**: 严格模式，强制类型注解，禁止未类型化定义
- **Ruff**: 集成了异步代码审计 (`ASYNC`) 和禁止盲捕获 (`BLE`)
