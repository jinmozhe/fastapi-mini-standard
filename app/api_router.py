"""
File: app/api_router.py
Description: 根 API 路由聚合层

本模块负责：
1. 聚合所有业务领域的 Router (auth, users, etc.)
2. 统一设置路由前缀 (如 /auth, /users)
3. 统一设置标签 (Tags) 用于 OpenAPI 文档分组

Author: jinmozhe
Created: 2025-12-05
"""

from fastapi import APIRouter

# 导入领域路由
from app.domains.auth.router import router as auth_router
from app.domains.users.router import router as users_router

# 创建根 API 路由
# 可以在这里统一设置 API 版本前缀，也可以在 main.py 中设置
api_router = APIRouter()

# ------------------------------------------------------------------------------
# 注册领域路由
# ------------------------------------------------------------------------------

# 1. 认证模块 (Auth Domain)
# 包含登录、刷新、登出等接口
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# 2. 用户模块 (Users Domain)
# 包含用户注册、查询、更新等接口
api_router.include_router(users_router, prefix="/users", tags=["users"])

# 未来新增模块示例:
# from app.domains.admin.router import router as admin_router
# api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
# from app.domains.orders.router import router as orders_router
# api_router.include_router(orders_router, prefix="/orders", tags=["orders"])
