"""
File: app/domains/addresses/service.py
Description: 收货地址核心业务逻辑

包含：
- 新增地址（首条自动设默认，超量拦截）
- 修改地址（含默认地址切换引擎）
- 删除地址（智能晋升补位）
- 查询地址列表与默认
- get_snapshot：供订单域固化地址快照

Author: jinmozhe
Created: 2026-04-12
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.db.models.address import UserAddress
from app.domains.addresses.constants import ADDRESS_MAX_COUNT, AddressError
from app.domains.addresses.repository import AddressRepository
from app.domains.addresses.schemas import AddressCreate, AddressSnapshot, AddressUpdate


class AddressService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AddressRepository(db)

    async def create_address(self, user_id: UUID, data: AddressCreate) -> UserAddress:
        """新建收货地址"""
        # 容量保护
        count = await self.repo.count_by_user(user_id)
        if count >= ADDRESS_MAX_COUNT:
            raise AppException(AddressError.MAX_LIMIT_REACHED)

        # 首条地址自动成为默认
        force_default = count == 0 or data.is_default

        if force_default:
            # 先将其他地址的 is_default 全部重置
            await self.repo.clear_default(user_id)

        address = UserAddress(
            user_id=user_id,
            label=data.label,
            receiver_name=data.receiver_name,
            phone_code=data.phone_code,
            mobile=data.mobile,
            country_code=data.country_code,
            province=data.province,
            province_code=data.province_code,
            city=data.city,
            city_code=data.city_code,
            district=data.district,
            district_code=data.district_code,
            street_address=data.street_address,
            postal_code=data.postal_code,
            is_default=force_default,
        )
        self.db.add(address)
        return address

    async def update_address(self, user_id: UUID, address_id: UUID, data: AddressUpdate) -> UserAddress:
        """全量修改地址"""
        address = await self.repo.get_by_id(address_id, user_id)
        if not address:
            raise AppException(AddressError.NOT_FOUND)

        # 如果请求设为默认，先清除其他
        if data.is_default and not address.is_default:
            await self.repo.clear_default(user_id)

        address.label = data.label
        address.receiver_name = data.receiver_name
        address.phone_code = data.phone_code
        address.mobile = data.mobile
        address.country_code = data.country_code
        address.province = data.province
        address.province_code = data.province_code
        address.city = data.city
        address.city_code = data.city_code
        address.district = data.district
        address.district_code = data.district_code
        address.street_address = data.street_address
        address.postal_code = data.postal_code
        address.is_default = data.is_default

        return address

    async def set_default(self, user_id: UUID, address_id: UUID) -> None:
        """切换默认地址（互斥引擎）"""
        address = await self.repo.get_by_id(address_id, user_id)
        if not address:
            raise AppException(AddressError.NOT_FOUND)

        if not address.is_default:
            # 原子事务：清除所有 → 设置目标
            await self.repo.clear_default(user_id)
            address.is_default = True

    async def delete_address(self, user_id: UUID, address_id: UUID) -> None:
        """
        物理删除地址
        - 如果删除的是默认地址，智能晋升剩余列表中最早创建的一条为新默认
        """
        address = await self.repo.get_by_id(address_id, user_id)
        if not address:
            raise AppException(AddressError.NOT_FOUND)

        was_default = address.is_default

        await self.db.delete(address)
        await self.db.flush()  # 先让删除生效，再做晋升

        if was_default:
            # 智能晋升剩余第一条为新默认
            await self.repo.promote_first_as_default(user_id)

    async def get_list(self, user_id: UUID) -> list[UserAddress]:
        """获取地址列表（默认地址排第一）"""
        return await self.repo.get_by_user(user_id)

    async def get_default(self, user_id: UUID) -> UserAddress | None:
        """获取默认地址（结算页快速拉取）"""
        return await self.repo.get_default(user_id)

    async def get_snapshot(self, user_id: UUID, address_id: UUID) -> AddressSnapshot:
        """
        地址快照生成器（供订单域调用）
        将地址数据序列化为快照字典，与 addresses 表解绑，永久固化在订单记录里。
        """
        address = await self.repo.get_by_id(address_id, user_id)
        if not address:
            raise AppException(AddressError.NOT_FOUND)

        return AddressSnapshot(
            receiver_name=address.receiver_name,
            phone_code=address.phone_code,
            mobile=address.mobile,
            country_code=address.country_code,
            province=address.province,
            province_code=address.province_code,
            city=address.city,
            city_code=address.city_code,
            district=address.district,
            district_code=address.district_code,
            street_address=address.street_address,
            postal_code=address.postal_code,
        )
