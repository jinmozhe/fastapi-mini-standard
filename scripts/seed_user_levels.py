"""
File: scripts/seed_user_levels.py
Description: 会员等级初始化种子脚本 (幂等)

功能：
1. 初始化会员等级配置 (五星/六星/七星/八星)
2. 支持重复运行，已存在的等级不会重复创建

用法：
    conda activate fastapi_env ; uv run python scripts/seed_user_levels.py

Author: jinmozhe
Created: 2026-04-12
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

# 将项目根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models.user_level import UserLevel


# --------------------------------------------------------------------------
# 等级配置种子数据
# --------------------------------------------------------------------------

LEVEL_SEEDS = [
    {
        "name": "五星会员",
        "rank_weight": 1,
        "discount_rate": Decimal("1.0000"),
        "upgrade_rules": {
            "op": "OR",
            "conditions": [
                {"metric": "total_consume", "operator": ">=", "value": 10000},
            ],
        },
        "commission_rules": [
            {"rank": 1, "first": "0", "second": "0", "third": "0"},
            {"rank": 2, "first": "0", "second": "0", "third": "0"},
            {"rank": 3, "first": "0", "second": "0", "third": "0"},
            {"rank": 4, "first": "0", "second": "0", "third": "0"},
        ],
        "reward_rules": [
            {"rank": 1, "first": "0", "second": "0", "third": "0"},
        ],
        "description": "基础会员等级",
        "is_active": True,
    },
    {
        "name": "六星会员",
        "rank_weight": 2,
        "discount_rate": Decimal("0.9500"),
        "upgrade_rules": {
            "op": "AND",
            "conditions": [
                {"metric": "total_consume", "operator": ">=", "value": 100000},
                {"metric": "total_invite_number", "operator": ">=", "value": 10},
            ],
        },
        "commission_rules": [
            {"rank": 1, "first": "3%", "second": "2%", "third": "0"},
            {"rank": 2, "first": "3%", "second": "2%", "third": "0"},
            {"rank": 3, "first": "3%", "second": "2%", "third": "0"},
            {"rank": 4, "first": "3%", "second": "2%", "third": "0"},
        ],
        "reward_rules": [
            {"rank": 1, "first": "0", "second": "0", "third": "0"},
        ],
        "description": "进阶会员，享受 95 折优惠",
        "is_active": True,
    },
    {
        "name": "七星会员",
        "rank_weight": 3,
        "discount_rate": Decimal("0.9000"),
        "upgrade_rules": {
            "op": "AND",
            "conditions": [
                {"metric": "total_consume", "operator": ">=", "value": 300000},
                {"metric": "total_invite_number", "operator": ">=", "value": 30},
            ],
        },
        "commission_rules": [
            {"rank": 1, "first": "5%", "second": "3%", "third": "0"},
            {"rank": 2, "first": "5%", "second": "3%", "third": "0"},
            {"rank": 3, "first": "5%", "second": "3%", "third": "0"},
            {"rank": 4, "first": "5%", "second": "3%", "third": "0"},
        ],
        "reward_rules": [
            {"rank": 2, "first": "100", "second": "50", "third": "0"},
        ],
        "description": "高级会员，享受 9 折优惠",
        "is_active": True,
    },
    {
        "name": "八星会员",
        "rank_weight": 4,
        "discount_rate": Decimal("0.8500"),
        "upgrade_rules": {
            "op": "AND",
            "conditions": [
                {"metric": "total_consume", "operator": ">=", "value": 1000000},
                {"metric": "total_invite_number", "operator": ">=", "value": 100},
            ],
        },
        "commission_rules": [
            {"rank": 1, "first": "10%", "second": "5%", "third": "0"},
            {"rank": 2, "first": "10%", "second": "5%", "third": "0"},
            {"rank": 3, "first": "10%", "second": "5%", "third": "0"},
            {"rank": 4, "first": "10%", "second": "5%", "third": "0"},
        ],
        "reward_rules": [
            {"rank": 2, "first": "200", "second": "100", "third": "0"},
            {"rank": 3, "first": "500", "second": "200", "third": "0"},
        ],
        "description": "顶级会员，享受 85 折优惠",
        "is_active": True,
    },
]


async def seed_user_levels() -> None:
    """幂等初始化会员等级配置"""
    engine = create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI), echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        async with session.begin():
            for seed in LEVEL_SEEDS:
                # 按 rank_weight 幂等检查
                result = await session.execute(
                    select(UserLevel).where(UserLevel.rank_weight == seed["rank_weight"])
                )
                existing = result.scalar_one_or_none()

                if existing:
                    print(f"  [跳过] {seed['name']} (rank_weight={seed['rank_weight']}) 已存在")
                    continue

                level = UserLevel(**seed)
                session.add(level)
                print(f"  [创建] {seed['name']} (rank_weight={seed['rank_weight']}, discount={seed['discount_rate']})")

        print("\n会员等级初始化完成!")

    await engine.dispose()


if __name__ == "__main__":
    print("=" * 60)
    print("会员等级种子数据初始化")
    print("=" * 60)
    asyncio.run(seed_user_levels())
