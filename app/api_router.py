"""
File: app/api_router.py
Description: 根 API 路由聚合层

本模块负责：
1. 聚合所有业务领域的 Router (auth, users, admin 等)
2. 统一设置路由前缀 (如 /auth, /users, /admin)
3. 统一设置标签 (Tags) 用于 OpenAPI 文档分组

Author: jinmozhe
Created: 2025-12-05
"""

from fastapi import APIRouter

# 导入领域路由
from app.domains.auth.router import router as auth_router
from app.domains.users.router import router as users_router
from app.domains.admin.router import router as admin_router
from app.domains.user_levels.router import router as user_levels_router
from app.domains.user_levels.admin_router import router as user_levels_admin
from app.domains.user_wallets.router import wallet_admin, wallet_router
from app.domains.products.router import product_admin, product_router
from app.domains.media.router import media_admin
from app.domains.carts.router import cart_router
from app.domains.addresses.router import address_router, address_admin
from app.domains.shipping.router import shipping_admin

# 创建根 API 路由
api_router = APIRouter()

# ------------------------------------------------------------------------------
# 注册领域路由
# ------------------------------------------------------------------------------

# 1. C端认证模块 (Auth Domain)
# 包含买家登录、刷新、登出等接口
api_router.include_router(auth_router, prefix="/auth", tags=["C端认证"])

# 2. 用户模块 (Users Domain)
# 包含用户注册、查询、更新等接口
api_router.include_router(users_router, prefix="/users", tags=["C端用户"])

# 3. C端会员等级模块 (User Levels Domain - C端展示)
# C端用户查看等级体系、权益对比
api_router.include_router(user_levels_router, prefix="/user_levels", tags=["C端会员等级"])

# 4. B端管理员模块 (Admin Domain)
# 包含管理员登录/刷新/登出、以及向前端输出角色权限树的接口
api_router.include_router(admin_router, prefix="/admin", tags=["B端管理员"])

# 5. B端会员等级管理模块 (User Levels Domain - B端管理)
# 后台管理员维护等级配置、人工干预用户等级
api_router.include_router(user_levels_admin, prefix="/admin/user_levels", tags=["B端会员等级管理"])

# 6. C端资金钱包模块 (User Wallets)
api_router.include_router(wallet_router, prefix="/user_wallets", tags=["C端我的钱包"])

# 7. B端后台资金监管体系 (User Wallets Admin)
api_router.include_router(wallet_admin, prefix="/admin/user_wallets", tags=["B端资金监管与干预"])

# 8. C端商品浏览 (Products)
api_router.include_router(product_router, prefix="/products", tags=["C端商品浏览"])

# 9. B端商品管理 (Products Admin)
api_router.include_router(product_admin, prefix="/admin/products", tags=["B端商品管理"])

# 10. B端媒体素材心 (Media Admin)
api_router.include_router(media_admin, prefix="/admin/media", tags=["B端媒体素材库"])

# 11. C端购物车 (Carts)
api_router.include_router(cart_router, prefix="/carts", tags=["C端购物车基础"])

# 12. C端收货地址 (Addresses)
api_router.include_router(address_router, prefix="/addresses", tags=["C端收货地址"])

# 13. B端收货地址管理 (Addresses Admin)
api_router.include_router(address_admin, prefix="/admin/addresses", tags=["B端收货地址管理"])

# 14. B端运费模板管理 (Shipping Templates)
api_router.include_router(shipping_admin, prefix="/admin/shipping-templates", tags=["B端运费模板"])



