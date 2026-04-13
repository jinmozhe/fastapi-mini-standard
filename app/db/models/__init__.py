"""
File: app/db/models/__init__.py
Description: ORM 模型注册表

本模块负责：
1. 导入所有业务模型 (User 等)
2. 导入基类 (Base, UUIDModel, Mixins)
3. 导出它们供 Alembic (env.py) 自动发现 metadata

注意：
每当新增一个 Model 文件，必须在此处导入，
否则 Alembic autogenerate 无法检测到新表。

Author: jinmozhe
Created: 2025-11-25
"""

# 1. 导入基类与组件
from app.db.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDBase,
    UUIDModel,
)

# 2. 导入业务模型
# 注意：新增模型必须在此处导入，否则 Alembic 无法识别
from app.db.models.user import User
from app.db.models.admin import SysAdmin, SysRole, SysPermission
from app.db.models.log import LoginLog, AuditLog
from app.db.models.user_level import UserLevel, UserLevelProfile, UserLevelRecord
from app.db.models.user_social import UserSocial
from app.db.models.user_wallet import UserBalanceLog, UserPointLog, UserWallet
from app.db.models.sms_log import SmsLog
from app.db.models.product import (
    Category,
    Product,
    ProductCategory,
    ProductSpec,
    ProductSku,
    ProductLevelPrice,
    ProductLevelCommission,
)
from app.db.models.product_view import ProductView
from app.db.models.media import MediaAsset
from app.db.models.cart import CartItem
from app.db.models.address import UserAddress
from app.db.models.shipping import ShippingTemplate, ShippingTemplateRegion
from app.db.models.payment import PaymentRecord
from app.db.models.order import Order, OrderItem
from app.db.models.commission import CommissionRecord
from app.db.models.refund import RefundRecord
from app.db.models.review import OrderReview

# 3. 显式导出 (供 Alembic 识别)
__all__ = [
    # 基类
    "Base",
    "UUIDBase",
    "UUIDModel",
    "TimestampMixin",
    "SoftDeleteMixin",
    # 业务模型
    "User",
    "SysAdmin",
    "SysRole",
    "SysPermission",    # 系统日志模型
    "LoginLog",
    "AuditLog",
    # 消息推送模型
    "SmsLog",
    # 资金钱包模型
    "UserWallet",
    "UserBalanceLog",
    "UserPointLog",
    # 用户等级体系
    "UserLevel",
    "UserLevelProfile",
    "UserLevelRecord",
    # 社交绑定
    "UserSocial",
    # 商品体系
    "Category",
    "Product",
    "ProductCategory",
    "ProductSpec",
    "ProductSku",
    "ProductLevelPrice",
    "ProductLevelCommission",
    # 媒体体系
    "MediaAsset",
    # 浏览足迹
    "ProductView",
    # 购物车体系
    "CartItem",
    # 收货地址
    "UserAddress",
    # 运费模板
    "ShippingTemplate",
    "ShippingTemplateRegion",
    # 支付记录
    "PaymentRecord",
    # 订单体系
    "Order",
    "OrderItem",
    # 佣金记录
    "CommissionRecord",
    # 售后退款
    "RefundRecord",
    # 订单评价
    "OrderReview",
]

