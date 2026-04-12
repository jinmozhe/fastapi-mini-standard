"""
File: app/domains/addresses/schemas.py
Description: 收货地址输入与输出验证模型

Author: jinmozhe
Created: 2026-04-12
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 请求模型
# ==============================================================================

class AddressCreate(BaseModel):
    """新建收货地址"""
    label: str | None = Field(default=None, max_length=20, description="标签（家/公司/自定义）")
    receiver_name: str = Field(..., min_length=1, max_length=50, description="收件人姓名")
    phone_code: str = Field(default="+86", max_length=10, description="手机区号（+86/+852/+853）")
    mobile: str = Field(..., min_length=5, max_length=20, description="手机号")
    country_code: str = Field(default="CN", max_length=10, description="国家编码")
    province: str = Field(..., min_length=1, max_length=50, description="省名称")
    province_code: str = Field(..., min_length=1, max_length=10, description="省行政编码")
    city: str = Field(..., min_length=1, max_length=50, description="市名称")
    city_code: str = Field(..., min_length=1, max_length=10, description="市行政编码")
    district: str = Field(..., min_length=1, max_length=50, description="区/县名称")
    district_code: str = Field(..., min_length=1, max_length=10, description="区行政编码")
    street_address: str = Field(..., min_length=1, max_length=200, description="详细街道+门牌号")
    postal_code: str | None = Field(default=None, max_length=20, description="邮政编码（可空）")
    is_default: bool = Field(default=False, description="是否设为默认")


class AddressUpdate(BaseModel):
    """全量修改收货地址（PUT）"""
    label: str | None = Field(default=None, max_length=20)
    receiver_name: str = Field(..., min_length=1, max_length=50)
    phone_code: str = Field(default="+86", max_length=10)
    mobile: str = Field(..., min_length=5, max_length=20)
    country_code: str = Field(default="CN", max_length=10)
    province: str = Field(..., min_length=1, max_length=50)
    province_code: str = Field(..., min_length=1, max_length=10)
    city: str = Field(..., min_length=1, max_length=50)
    city_code: str = Field(..., min_length=1, max_length=10)
    district: str = Field(..., min_length=1, max_length=50)
    district_code: str = Field(..., min_length=1, max_length=10)
    street_address: str = Field(..., min_length=1, max_length=200)
    postal_code: str | None = Field(default=None, max_length=20)
    is_default: bool = Field(default=False)


# ==============================================================================
# 响应模型
# ==============================================================================

class AddressRead(BaseModel):
    """收货地址响应"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    label: str | None
    receiver_name: str
    phone_code: str
    mobile: str
    country_code: str
    province: str
    province_code: str
    city: str
    city_code: str
    district: str
    district_code: str
    street_address: str
    postal_code: str | None
    is_default: bool
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# 订单快照结构（供订单域调用序列化地址）
# ==============================================================================

class AddressSnapshot(BaseModel):
    """
    地址快照（订单下单时固化，与 addresses 表彻底解绑）
    """
    receiver_name: str
    phone_code: str
    mobile: str
    country_code: str
    province: str
    province_code: str
    city: str
    city_code: str
    district: str
    district_code: str
    street_address: str
    postal_code: str | None
