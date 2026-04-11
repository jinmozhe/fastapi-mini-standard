"""
File: alembic/env.py
Description: Alembic 迁移环境配置 - 同步版本 (Windows 完全兼容)

策略：
- 迁移 (Migration): 使用 psycopg (Sync) -> 稳定，无 EventLoop 问题，兼容 SQLAlchemy 2.0
- 运行 (Runtime): 使用 asyncpg (Async) -> 高性能

Author: jinmozhe
Created: 2025-11-26
Updated: 2026-01-30 (Upgrade to Psycopg 3)
"""

import sys
from logging.config import fileConfig
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine, pool

from alembic import context  # type: ignore

# ------------------------------------------------------------------------------
# 0. 将项目根目录加入 sys.path
# ------------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

# ------------------------------------------------------------------------------
# 1. 导入项目配置与模型
# ------------------------------------------------------------------------------
from app.core.config import settings
from app.db.models import Base

# Alembic Config 对象
config = context.config

# 2. 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ------------------------------------------------------------------------------
# 3. 构建同步数据库 URL
# ------------------------------------------------------------------------------
try:
    # 优先尝试从组件手动构建，以确保对特殊字符（如密码中的 @）进行正确编码
    db_user = settings.POSTGRES_USER or "postgres"
    db_password = settings.POSTGRES_PASSWORD or ""
    db_host = settings.POSTGRES_SERVER or "localhost"
    db_port = settings.POSTGRES_PORT or 5432
    db_name = settings.POSTGRES_DB or "postgres"

    # 关键：对密码进行 URL 编码，防止密码中包含 '@' 等字符破坏连接串结构
    encoded_password = quote_plus(db_password)

    # [Standard Update] 使用 postgresql+psycopg (Psycopg 3)
    sync_uri = f"postgresql+psycopg://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"

except AttributeError:
    # 备选方案：如果 settings 结构不同，尝试直接从异步 URI 转换
    # (假设原 URI 格式标准，无特殊字符干扰)
    async_uri = str(settings.SQLALCHEMY_DATABASE_URI)
    # [Standard Update] 替换为 postgresql+psycopg
    sync_uri = async_uri.replace("postgresql+asyncpg", "postgresql+psycopg")

# 转义 % 字符 (configparser 既然用了，就需要处理插值符号)
escaped_uri = sync_uri.replace("%", "%%")

# 【修复】这里去掉了原代码中的空格: "sqlalchemy.url"
config.set_main_option("sqlalchemy.url", escaped_uri)

# 4. 指定目标元数据
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式迁移：生成 SQL 脚本而不实际连接数据库"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式迁移：连接数据库并执行迁移"""
    # 使用同步引擎 create_engine
    # 修复 Pylance 报错：get_main_option 可能返回 None，添加 'or ""' 确保它是字符串
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url") or "",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


# ------------------------------------------------------------------------------
# 执行迁移
# ------------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
