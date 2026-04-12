"""
File: app/domains/user_levels/service.py
Description: 用户等级领域业务逻辑层

核心功能：
1. B端等级配置 CRUD
2. C端等级体系查询
3. 升降级规则引擎 (AST 递归求解器)
4. 人工等级干预

Author: jinmozhe
Created: 2026-04-12
"""

import uuid
from decimal import Decimal
from typing import Any

from loguru import logger

from app.core.exceptions import AppException
from app.db.models.user_level import UserLevel, UserLevelProfile, UserLevelRecord
from app.domains.user_levels.constants import UserLevelError
from app.domains.user_levels.repository import (
    UserLevelProfileRepository,
    UserLevelRecordRepository,
    UserLevelRepository,
)


class UserLevelService:
    """
    用户等级业务服务层

    关键设计：
    - 升级规则引擎通过 JSONB AST 递归求解，支持 AND/OR 任意组合
    - 升降级判定统一走 evaluate_user_level() 方法
    - is_manual=True 的用户跳过自动升降级
    """

    def __init__(
        self,
        level_repo: UserLevelRepository,
        profile_repo: UserLevelProfileRepository,
        record_repo: UserLevelRecordRepository,
    ):
        self.level_repo = level_repo
        self.profile_repo = profile_repo
        self.record_repo = record_repo

    # ==========================================================================
    # B端管理操作
    # ==========================================================================

    async def create_level(self, **kwargs: Any) -> UserLevel:
        """创建会员等级 (含唯一性校验)"""
        # 名称唯一性校验
        existing_name = await self.level_repo.get_by_name(kwargs["name"])
        if existing_name:
            raise AppException(UserLevelError.LEVEL_NAME_EXIST)

        # 权重唯一性校验
        existing_rank = await self.level_repo.get_by_rank_weight(kwargs["rank_weight"])
        if existing_rank:
            raise AppException(UserLevelError.LEVEL_RANK_EXIST)

        level = UserLevel(**kwargs)
        return await self.level_repo.create(level)

    async def update_level(
        self, level_id: uuid.UUID, **kwargs: Any
    ) -> UserLevel:
        """更新会员等级配置"""
        level = await self.level_repo.get_by_id(level_id)
        if not level:
            raise AppException(UserLevelError.LEVEL_NOT_FOUND)

        # 如果修改了名称，检查唯一性
        if "name" in kwargs and kwargs["name"] != level.name:
            existing = await self.level_repo.get_by_name(kwargs["name"])
            if existing:
                raise AppException(UserLevelError.LEVEL_NAME_EXIST)

        # 如果修改了权重，检查唯一性
        if "rank_weight" in kwargs and kwargs["rank_weight"] != level.rank_weight:
            existing = await self.level_repo.get_by_rank_weight(kwargs["rank_weight"])
            if existing:
                raise AppException(UserLevelError.LEVEL_RANK_EXIST)

        level.update(**kwargs)
        return level

    async def delete_level(self, level_id: uuid.UUID) -> None:
        """删除等级 (含关联用户检查)"""
        level = await self.level_repo.get_by_id(level_id)
        if not level:
            raise AppException(UserLevelError.LEVEL_NOT_FOUND)

        # 检查是否有用户关联到此等级
        user_count = await self.profile_repo.count_by_level_id(level_id)
        if user_count > 0:
            raise AppException(UserLevelError.LEVEL_HAS_USERS)

        await self.level_repo.delete(level)

    async def get_all_levels(self) -> list[UserLevel]:
        """获取所有等级 (B端管理用，含停用)"""
        return await self.level_repo.get_all()

    async def get_level_detail(self, level_id: uuid.UUID) -> UserLevel:
        """获取等级详情"""
        level = await self.level_repo.get_by_id(level_id)
        if not level:
            raise AppException(UserLevelError.LEVEL_NOT_FOUND)
        return level

    # ==========================================================================
    # C端查询
    # ==========================================================================

    async def get_active_levels(self) -> list[UserLevel]:
        """获取所有启用的等级 (C端用，按权重升序)"""
        return await self.level_repo.get_all_active()

    async def get_user_profile(self, user_id: uuid.UUID) -> UserLevelProfile | None:
        """获取用户的等级档案"""
        return await self.profile_repo.get_by_user_id(user_id)

    async def get_user_profile_detail(self, user_id: uuid.UUID) -> dict[str, Any]:
        """获取用户完整的等级档案详情 (带上等级的基础信息)"""
        profile = await self.profile_repo.get_by_user_id(user_id)
        if not profile:
            # 返回全0的默认状态
            return {
                "total_consume": Decimal("0"),
                "total_points": 0,
                "total_buy_number": 0,
                "total_invite_number": 0,
                "is_manual": False
            }
        
        data = {
            "total_consume": profile.total_consume,
            "total_points": profile.total_points,
            "total_buy_number": profile.total_buy_number,
            "total_invite_number": profile.total_invite_number,
            "is_manual": profile.is_manual,
        }

        if profile.level_id:
            level = await self.level_repo.get_by_id(profile.level_id)
            if level:
                data.update({
                    "level_name": level.name,
                    "level_rank": level.rank_weight,
                    "discount_rate": level.discount_rate,
                    "icon_url": level.icon_url,
                })
        return data

    # ==========================================================================
    # 人工干预
    # ==========================================================================

    async def override_user_level(
        self,
        user_id: uuid.UUID,
        level_id: uuid.UUID,
        remark: str | None = None,
    ) -> UserLevelProfile:
        """
        后台强制指定用户等级，设置 is_manual=True 锁定。
        系统自动升降级程序将跳过此用户。
        """
        # 验证目标等级存在
        level = await self.level_repo.get_by_id(level_id)
        if not level:
            raise AppException(UserLevelError.LEVEL_NOT_FOUND)

        # 获取或创建用户等级档案
        profile = await self.profile_repo.get_by_user_id(user_id)
        old_level_id = None

        if profile:
            old_level_id = profile.level_id
            profile.level_id = level_id
            profile.is_manual = True
        else:
            profile = UserLevelProfile(
                user_id=user_id,
                level_id=level_id,
                is_manual=True,
            )
            await self.profile_repo.create(profile)

        # 写入变动记录
        record = UserLevelRecord(
            user_id=user_id,
            old_level_id=old_level_id,
            new_level_id=level_id,
            change_type="MANUAL",
            remark=remark or "后台管理员手工指定等级",
        )
        await self.record_repo.create(record)

        logger.info(
            f"[LevelOverride] user_id={user_id} -> level={level.name} (manual lock)"
        )
        return profile

    async def release_manual_lock(
        self, user_id: uuid.UUID
    ) -> UserLevelProfile:
        """解除人工锁定，恢复系统自动计算"""
        profile = await self.profile_repo.get_by_user_id(user_id)
        if not profile:
            raise AppException(UserLevelError.PROFILE_NOT_FOUND)

        profile.is_manual = False
        logger.info(f"[LevelRelease] user_id={user_id} manual lock released")
        return profile

    # ==========================================================================
    # 升降级规则引擎 (AST 递归求解器)
    # ==========================================================================

    async def evaluate_user_level(self, user_id: uuid.UUID) -> UserLevelProfile:
        """
        核心引擎：根据用户的当前指标重新计算应处等级。

        算法流程：
        1. 获取用户的 user_level_profiles 指标数据
        2. 获取所有启用等级 (按 rank_weight 降序)
        3. 从最高等级开始逐级匹配，找到第一个满足条件的等级
        4. 如果新等级与当前等级不同，执行升/降级并写入记录

        注意：is_manual=True 的用户直接跳过
        """
        profile = await self.profile_repo.get_by_user_id(user_id)
        if not profile:
            logger.warning(f"[LevelEvaluate] 用户 {user_id} 无等级档案，跳过")
            return profile  # type: ignore

        # 人工锁定用户跳过自动计算
        if profile.is_manual:
            logger.debug(f"[LevelEvaluate] 用户 {user_id} 已人工锁定，跳过自动计算")
            return profile

        # 获取所有启用等级 (升序)
        all_levels = await self.level_repo.get_all_active()
        if not all_levels:
            return profile

        # 构建用户指标字典 (供规则引擎使用)
        user_metrics = {
            "total_consume": float(profile.total_consume),
            "total_points": profile.total_points,
            "total_buy_number": profile.total_buy_number,
            "total_invite_number": profile.total_invite_number,
        }

        # 从最高等级开始逐级匹配 (降序遍历)
        matched_level: UserLevel | None = None
        for level in reversed(all_levels):
            if level.upgrade_rules and self._evaluate_rules(
                level.upgrade_rules, user_metrics
            ):
                matched_level = level
                break

        # 未匹配到任何等级，看最低等级是否无条件
        if not matched_level:
            lowest = all_levels[0]
            if not lowest.upgrade_rules:
                matched_level = lowest

        # 判断是否需要变动
        if matched_level and matched_level.id != profile.level_id:
            old_level_id = profile.level_id
            old_rank = 0

            # 获取旧等级的 rank_weight 用于判断升/降
            if old_level_id:
                old_level = await self.level_repo.get_by_id(old_level_id)
                if old_level:
                    old_rank = old_level.rank_weight

            change_type = (
                "UPGRADE" if matched_level.rank_weight > old_rank else "DOWNGRADE"
            )

            profile.level_id = matched_level.id

            # 写入变动记录
            record = UserLevelRecord(
                user_id=user_id,
                old_level_id=old_level_id,
                new_level_id=matched_level.id,
                change_type=change_type,
                remark=f"系统自动{'升级' if change_type == 'UPGRADE' else '降级'}至 {matched_level.name}",
            )
            await self.record_repo.create(record)

            logger.info(
                f"[LevelEvaluate] user_id={user_id} {change_type}: "
                f"rank {old_rank} -> {matched_level.rank_weight} ({matched_level.name})"
            )

        return profile

    @staticmethod
    def _evaluate_rules(rules: dict[str, Any], metrics: dict[str, Any]) -> bool:
        """
        递归求解 JSONB 规则树 (AST 引擎)

        支持的规则结构：
        - 叶子节点: {"metric": "total_consume", "operator": ">=", "value": 10000}
        - 分支节点: {"op": "AND"/"OR", "conditions": [...]}

        Args:
            rules: 规则树节点
            metrics: 用户当前指标字典

        Returns:
            是否满足该规则节点
        """
        # 叶子节点：直接比较
        if "metric" in rules:
            metric_name = rules["metric"]
            operator = rules["operator"]
            threshold = rules["value"]

            actual_value = metrics.get(metric_name, 0)

            if operator == ">=":
                return actual_value >= threshold
            elif operator == ">":
                return actual_value > threshold
            elif operator == "<=":
                return actual_value <= threshold
            elif operator == "<":
                return actual_value < threshold
            elif operator == "==":
                return actual_value == threshold
            else:
                logger.warning(f"[RuleEngine] 未知运算符: {operator}")
                return False

        # 分支节点：递归求解
        op = rules.get("op", "AND").upper()
        conditions = rules.get("conditions", [])

        if not conditions:
            return True  # 无条件默认通过

        if op == "AND":
            return all(
                UserLevelService._evaluate_rules(cond, metrics) for cond in conditions
            )
        elif op == "OR":
            return any(
                UserLevelService._evaluate_rules(cond, metrics) for cond in conditions
            )
        else:
            logger.warning(f"[RuleEngine] 未知逻辑运算: {op}")
            return False
