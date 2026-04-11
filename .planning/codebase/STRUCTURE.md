# STRUCTURE.md — 项目目录结构

## 根目录
```
e:\fastapi\fastapi-mini-standard\
├── .agent/                      # GSD 工作流引擎（提交到 Git）
│   ├── skills/                  # GSD 技能定义
│   ├── get-shit-done/           # GSD 核心工作流
│   ├── scratch/                 # AI 临时沙盒（.gitignore 排除）
│   └── settings.json            # GSD 配置
├── .claude/skills/              # 项目级 AI 开发规范
│   └── fastapi-standard.md      # FastAPI 工程标准（实现期检查清单）
├── .planning/codebase/          # GSD 代码库地图（本文件所在目录）
├── .venv/                       # Python 虚拟环境（不提交）
├── .vscode/                     # VS Code 配置（不提交）
├── alembic/                     # 数据库迁移
│   ├── env.py                   # 迁移环境配置（同步 psycopg 驱动）
│   ├── script.py.mako           # 迁移脚本模板
│   └── versions/                # 迁移版本文件（必须提交）
├── app/                         # 应用主目录
├── .env                         # 环境变量（不提交，含敏感信息）
├── .env.example                 # 环境变量模板（提交）
├── .gitignore                   # Git 忽略规则
├── .importlinter                # 架构约束（禁止跨域导入）
├── alembic.ini                  # Alembic 入口配置
├── pyproject.toml               # 项目元信息 + 工具配置
├── uv.lock                      # 精确版本锁（提交）
├── Dockerfile                   # 容器化
├── docker-compose.yml           # Docker 编排
└── README.md                    # 项目文档
```

## app/ 应用目录
```
app/
├── __init__.py
├── main.py                      # FastAPI 工厂函数 + Lifespan
├── api_router.py                # 路由聚合（挂载所有 domain router）
├── api/
│   └── deps.py                  # 全局依赖注入（DBSession, CurrentUser, SuperUser）
├── core/                        # 横切关注点
│   ├── config.py                # Settings（pydantic-settings, .env 加载）
│   ├── security.py              # Argon2id 密码哈希 + JWT 签发
│   ├── exceptions.py            # AppException + 全局异常处理器（4 层拦截）
│   ├── error_code.py            # BaseErrorCode 枚举基类 + SystemErrorCode
│   ├── response.py              # ResponseModel[T] 统一响应信封
│   ├── middleware.py            # RequestLogMiddleware + CORS 注册
│   ├── logging.py               # Loguru 配置（接管 Uvicorn 日志）
│   └── redis.py                 # Redis 单例客户端 + 依赖注入
├── db/
│   ├── models/
│   │   ├── __init__.py          # 导出 Base（Alembic 扫描入口）
│   │   ├── base.py              # ORM 基类（UUIDBase, UUIDModel, Mixins, sort_order 排序）
│   │   └── user.py              # User 模型（phone_code + mobile 复合唯一）
│   ├── repositories/
│   │   └── base.py              # BaseRepository[T, CreateSchema, UpdateSchema] 泛型仓储
│   └── session.py               # AsyncEngine + AsyncSessionLocal 工厂
├── domains/
│   ├── auth/                    # 认证领域
│   │   ├── router.py            # POST /login, /register, /refresh, /logout
│   │   ├── schemas.py           # LoginRequest, RegisterRequest, Token, RefreshRequest
│   │   ├── service.py           # AuthService（注册、登录、刷新、登出）
│   │   └── constants.py         # AuthError 错误码 + AuthMsg 消息常量
│   └── users/                   # 用户领域
│       ├── router.py            # GET /me, PUT /me, DELETE /me, GET /{id}, GET /list
│       ├── schemas.py           # UserBase, UserUpdate, UserRead + 校验常量
│       ├── service.py           # UserService（查询、更新、软删除）
│       ├── repository.py        # UserRepository（get_by_mobile, get_by_email 等）
│       └── constants.py         # UserError 错误码 + UserMsg 消息常量
├── services/                    # 跨领域服务（预留，当前为空）
│   └── __init__.py
├── static/                      # 静态资源
│   ├── redoc.standalone.js      # ReDoc 本地化 JS
│   └── favicon.png              # 网站图标
└── utils/                       # 工具函数（预留）
```

## 关键路径速查
| 场景 | 文件 |
|---|---|
| 添加新业务域 | `app/domains/{name}/` (router, schemas, service, repository, constants) + `app/api_router.py` 注册 |
| 新增 ORM 模型 | `app/db/models/{name}.py` + `app/db/models/__init__.py` 导入 |
| 修改全局配置 | `app/core/config.py` + `.env` |
| 新增错误码 | `app/domains/{name}/constants.py` (继承 `BaseErrorCode`) |
| Alembic 迁移 | `alembic revision --autogenerate -m "..."` + `alembic upgrade head` |
