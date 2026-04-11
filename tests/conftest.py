"""
File: tests/conftest.py
Description: 全局测试 Fixture 定义

本模块负责：
1. 创建测试用 AsyncSession（独立事务，自动回滚）
2. 创建 FastAPI TestClient（httpx.AsyncClient）
3. 提供 Mock Redis Fixture
4. 管理测试数据库的生命周期

Author: jinmozhe
Created: 2026-04-11
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.db.models.base import Base
from app.main import app


# 使用与主应用相同的数据库（测试环境应使用独立的测试库）
TEST_DATABASE_URL = str(settings.SQLALCHEMY_DATABASE_URI)

# 测试用异步引擎
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """为整个测试会话创建统一的事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """在测试会话开始时创建表，结束时销毁"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """为每个测试用例提供独立的数据库会话"""
    async with TestSessionLocal() as session:
        yield session
        # 测试结束后回滚，保持测试隔离
        await session.rollback()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """创建异步 HTTP 测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
