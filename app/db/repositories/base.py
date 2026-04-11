"""
File: app/db/repositories/base.py
Description: 通用异步 Repository 基类 (CRUD)

本模块定义了 BaseRepository，封装了通用的 CRUD 操作。
所有领域的 Repository 应继承此类，以减少样板代码。

特性：
- 泛型支持: BaseRepository[ModelType, CreateSchemaType, UpdateSchemaType]
- 纯异步: 基于 sqlalchemy.ext.asyncio
- 安全增强: update 操作自动过滤核心系统字段 (id, created_at)，但允许修改业务状态 (is_deleted)

Author: jinmozhe
Created: 2025-11-25
"""

from typing import Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.base import Base

# 定义泛型变量
ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    通用 CRUD 仓储基类。

    参数:
    - ModelType: SQLAlchemy 模型类 (如 User)
    - CreateSchemaType: 创建数据的 Pydantic 模型 (如 UserCreate)
    - UpdateSchemaType: 更新数据的 Pydantic 模型 (如 UserUpdate)
    """

    # 受保护的字段，禁止通过通用 update 方法修改
    # 注意：is_deleted / deleted_at 未在此列，允许 Service 层通过 update 实现软删除
    PROTECTED_FIELDS: ClassVar[set[str]] = {"id", "created_at", "updated_at"}

    def __init__(self, model: type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    # --------------------------------------------------------------------------
    # 查询操作 (Read)
    # --------------------------------------------------------------------------

    async def get(self, id: Any) -> ModelType | None:
        """根据主键 ID 查询单条记录"""
        return await self.session.get(self.model, id)

    async def exists(self, id: Any) -> bool:
        """
        检查记录是否存在。

        Args:
            id: 主键 ID

        Returns:
            bool: 存在返回 True，否则返回 False
        """
        return await self.get(id) is not None

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        """
        分页查询记录列表。

        Args:
            skip: 跳过的记录数（偏移量）
            limit: 返回的最大记录数

        Returns:
            list[ModelType]: 记录列表
        """
        stmt = select(self.model).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        """
        获取记录总数。

        Returns:
            int: 记录总数
        """
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    # --------------------------------------------------------------------------
    # 写入操作 (Create / Update / Delete)
    # --------------------------------------------------------------------------

    async def create(self, obj_in: CreateSchemaType) -> ModelType:
        """
        创建新记录。

        自动将 Pydantic schema 转换为 dict，并创建 ORM 对象。
        注意：此方法会自动 flush 到数据库以获取 ID，但不会 commit（由 Service 层控制事务）。
        """
        obj_in_data = obj_in.model_dump(exclude_unset=True)
        db_obj = self.model(**obj_in_data)

        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)

        return db_obj

    async def update(
        self, db_obj: ModelType, obj_in: UpdateSchemaType | dict[str, Any]
    ) -> ModelType:
        """
        更新现有记录。

        支持传入 UpdateSchema 或 字典。
        会自动过滤 PROTECTED_FIELDS 中的敏感字段(如 id, created_at)。
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        # 优先调用模型基类的 .update() 方法 (如果存在)
        if hasattr(db_obj, "update"):
            # 过滤掉受保护的字段，防止意外修改
            safe_data = {
                k: v for k, v in update_data.items() if k not in self.PROTECTED_FIELDS
            }
            db_obj.update(**safe_data)  # type: ignore[union-attr]
        else:
            # 作为兜底方案：模型未实现 .update() 时逐字段赋值
            for field, value in update_data.items():
                if field in self.PROTECTED_FIELDS:
                    continue
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)

        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)

        return db_obj

    async def delete(self, id: Any) -> ModelType | None:
        """
        物理删除记录。

        注意：
        如果是需要软删除的模型 (继承了 SoftDeleteMixin)，建议不要直接调用此方法，
        而是通过 update 方法设置 is_deleted=True。
        """
        db_obj = await self.get(id)
        if db_obj:
            await self.session.delete(db_obj)
            await self.session.flush()
        return db_obj
