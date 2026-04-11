# 测试 (TESTING)

## 测试框架

| 工具 | 版本要求 | 用途 |
|---|---|---|
| pytest | >=8.2.0 | 测试框架 |
| pytest-asyncio | >=0.23.0 | 异步测试支持 |
| httpx | >=0.27.0 | 异步 HTTP 测试客户端 |

## Pytest 配置

```toml
# pyproject.toml
[tool.pytest.ini_options]
minversion = "6.0"
addopts = "-ra -q --asyncio-mode=auto"
testpaths = ["tests"]
python_files = "test_*.py"
asyncio_default_fixture_loop_scope = "session"
```

关键设置:
- `--asyncio-mode=auto`: 自动标记异步测试函数
- `asyncio_default_fixture_loop_scope = "session"`: 默认 fixture 作用域为 session
- 测试目录: `tests/` (根目录级别)

## 当前测试状态

**⚠️ `tests/` 目录尚未创建。** 项目当前处于模板阶段, 测试基础设施已在配置中就绪, 但尚未编写实际测试。

## 预期测试模式

### 单元测试

基于项目架构, 预期的测试模式:

```python
# 使用 httpx.AsyncClient 测试 API
async with AsyncClient(app=app, base_url="http://test") as ac:
    response = await ac.post("/api/v1/auth/login", json={...})
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "success"
```

### Mock 策略

- **数据库**: Override `get_db` 依赖, 注入测试 Session
- **Redis**: Override `get_redis` 依赖, 注入 Mock Redis
- **密码哈希**: 测试时可降低 Argon2 参数加速

### 测试覆盖范围 (待实现)

| 层级 | 测试类型 | 关注点 |
|---|---|---|
| Router | API 集成测试 | 端点响应格式、HTTP 状态码 |
| Service | 单元测试 | 业务逻辑、唯一性校验、事务 |
| Repository | 集成测试 | SQL 查询正确性、软删除过滤 |
| Core | 单元测试 | JWT、密码哈希、错误处理 |

## 代码质量工具

### Ruff (Lint + Format)

```bash
# Lint
ruff check .

# Format
ruff format .
```

### Mypy (类型检查)

```bash
mypy app/
```

### import-linter (架构约束)

```bash
lint-imports
```

验证内容:
1. 领域模块间独立性
2. 分层架构顺序
3. 无循环依赖
4. Service 不直接导入 ORM Models

### Pre-commit (Git Hooks)

配置了 `pre-commit>=3.7.0`, 预期与 Ruff + Mypy 集成。
