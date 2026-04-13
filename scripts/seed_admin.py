"""
File: scripts/seed_admin.py
Description: 超级管理员初始化种子脚本

用途：
  在全新部署或开发环境中，一键初始化第一个超级管理员账号、
  完整权限树 (sys_permissions)、超级管理员角色 (sys_roles)，并完成绑定。

幂等性设计：
  脚本可以重复运行，已存在的数据会跳过，不会发生重复插入错误。

使用方式：
  conda activate fastapi_env
  uv run python scripts/seed_admin.py

  自定义账号密码：
  SEED_ADMIN_USERNAME=root SEED_ADMIN_PASSWORD=mypassword uv run python scripts/seed_admin.py

Author: jinmozhe
Created: 2026-04-12
Updated: 2026-04-13 (覆盖全部 B 端 RBAC 权限点)
"""

import asyncio
import os
import sys
from pathlib import Path

# 强制设定标准输入输出为 UTF-8（解决 Windows 命令行 GBK 编码问题）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# 将项目根目录加入 sys.path（保证可以 import app.* 模块）
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import insert, select

from app.core.security import get_password_hash
from app.db.models.admin import (
    SysAdmin,
    SysPermission,
    SysRole,
    sys_admin_role_table,
    sys_role_permission_table,
)
from app.db.session import AsyncSessionLocal

# ==============================================================================
# 配置项：从环境变量读取，开发环境有默认值
# ==============================================================================

SEED_USERNAME: str = os.getenv("SEED_ADMIN_USERNAME", "admin")
SEED_PASSWORD: str = os.getenv("SEED_ADMIN_PASSWORD", "Admin@2026!")
SEED_REAL_NAME: str = os.getenv("SEED_ADMIN_REAL_NAME", "超级管理员")

# ==============================================================================
# 完整权限点定义（覆盖全部 B 端操作）
# 格式：(code, name, type)
#
# type 说明：
#   menu   = 菜单级（左侧导航栏可见）
#   button = 按钮级（具体操作权限）
# ==============================================================================

INITIAL_PERMISSIONS: list[tuple[str, str, str]] = [
    # ========== 仪表盘 ==========
    ("dashboard:view",          "仪表盘",               "menu"),

    # ========== 管理员管理 ==========
    ("admin:view",              "管理员列表",           "menu"),
    ("admin:create",            "新增管理员",           "button"),
    ("admin:edit",              "编辑管理员",           "button"),

    # ========== 角色管理 ==========
    ("role:view",               "角色列表",             "menu"),
    ("role:create",             "新增角色",             "button"),
    ("role:edit",               "编辑角色",             "button"),

    # ========== 权限管理 ==========
    ("permission:view",         "权限列表",             "menu"),

    # ========== 用户管理 ==========
    ("user:view",               "用户列表",             "menu"),
    ("user:create",             "新增用户",             "button"),
    ("user:edit",               "编辑用户",             "button"),
    ("user:ban",                "封禁/解封用户",        "button"),

    # ========== 会员等级管理 ==========
    ("user_level:view",         "会员等级列表",         "menu"),
    ("user_level:create",       "新增会员等级",         "button"),
    ("user_level:edit",         "编辑会员等级",         "button"),
    ("user_level:delete",       "删除会员等级",         "button"),
    ("user_level:override",     "强制指定用户等级",     "button"),

    # ========== 资金监管 ==========
    ("wallet:view",             "资金监管列表",         "menu"),
    ("wallet:recharge",         "手工充值",             "button"),
    ("wallet:deduct",           "手工扣款",             "button"),
    ("wallet:grant_points",     "手工发放积分",         "button"),
    ("wallet:revoke_points",    "手工扣除积分",         "button"),

    # ========== 商品管理 ==========
    ("product:view",            "商品列表",             "menu"),
    ("product:create",          "新增商品",             "button"),
    ("product:edit",            "编辑商品",             "button"),
    ("product:delete",          "删除商品",             "button"),
    ("product:sku",             "SKU 管理",             "button"),
    ("product:category",        "分类管理",             "button"),

    # ========== 媒体素材库 ==========
    ("media:view",              "媒体素材列表",         "menu"),
    ("media:upload",            "上传素材",             "button"),
    ("media:delete",            "删除素材",             "button"),

    # ========== 收货地址管理 ==========
    ("address:view",            "收货地址列表",         "menu"),

    # ========== 运费模板 ==========
    ("shipping:view",           "运费模板列表",         "menu"),
    ("shipping:create",         "新增运费模板",         "button"),
    ("shipping:edit",           "编辑运费模板",         "button"),
    ("shipping:delete",         "删除运费模板",         "button"),

    # ========== 订单管理 ==========
    ("order:view",              "订单列表",             "menu"),
    ("order:detail",            "订单详情",             "button"),
    ("order:cancel",            "强制取消订单",         "button"),

    # ========== 履约管理 ==========
    ("fulfillment:view",        "履约管理",             "menu"),
    ("fulfillment:ship",        "发货",                 "button"),
    ("fulfillment:batch_ship",  "批量发货",             "button"),
    ("fulfillment:auto_confirm","自动确认收货",         "button"),

    # ========== 售后管理 ==========
    ("refund:view",             "售后列表",             "menu"),
    ("refund:detail",           "售后详情",             "button"),
    ("refund:review",           "审核退款",             "button"),
    ("refund:confirm_return",   "确认收到退货",         "button"),

    # ========== 评价管理 ==========
    ("review:view",             "评价列表",             "menu"),
    ("review:reply",            "回复评价",             "button"),
    ("review:visibility",       "设置评价可见性",       "button"),

    # ========== 推荐关系管理 ==========
    ("referral:view",           "推荐关系列表",         "menu"),
    ("referral:bind",           "手动绑定推荐人",       "button"),
    ("referral:unbind",         "解除推荐关系",         "button"),

    # ========== 提现管理 ==========
    ("withdrawal:view",         "提现列表",             "menu"),
    ("withdrawal:detail",       "提现详情",             "button"),
    ("withdrawal:review",       "审核提现",             "button"),
    ("withdrawal:complete",     "确认打款完成",         "button"),

    # ========== 日志审计 ==========
    ("log:view",                "日志查看",             "menu"),

    # ========== 财务报表 ==========
    ("finance:view",            "财务报表",             "menu"),
    ("finance:export",          "财务数据导出",         "button"),
]

SUPER_ADMIN_ROLE_CODE: str = "SUPER_ADMIN"
SUPER_ADMIN_ROLE_NAME: str = "超级管理员"


# ==============================================================================
# 核心初始化逻辑
# ==============================================================================


async def seed() -> None:
    print("=" * 60)
    print("[START] 开始执行超级管理员初始化种子脚本")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        # ------------------------------------------------------------------
        # Step 1：初始化基础权限点（幂等）
        # ------------------------------------------------------------------
        print("\n[STEP 1] 初始化基础权限点 (sys_permissions)...")
        perm_ids: list[str] = []
        created_count = 0
        skipped_count = 0

        for code, name, ptype in INITIAL_PERMISSIONS:
            existing = await session.execute(
                select(SysPermission).where(SysPermission.code == code)
            )
            perm = existing.scalar_one_or_none()

            if perm:
                skipped_count += 1
                perm_ids.append(str(perm.id))
            else:
                new_perm = SysPermission(code=code, name=name, type=ptype)
                session.add(new_perm)
                await session.flush()
                perm_ids.append(str(new_perm.id))
                created_count += 1
                print(f"  [OK]   创建权限点: [{code}] {name}")

        print(f"  新增 {created_count} 个，跳过 {skipped_count} 个，总计 {len(perm_ids)} 个权限点")

        # ------------------------------------------------------------------
        # Step 2：创建超级管理员角色（幂等）
        # ------------------------------------------------------------------
        print(f"\n[STEP 2] 初始化角色 [{SUPER_ADMIN_ROLE_CODE}]...")
        result = await session.execute(
            select(SysRole).where(SysRole.code == SUPER_ADMIN_ROLE_CODE)
        )
        role = result.scalar_one_or_none()

        if role:
            print(f"  [SKIP] 已存在: {SUPER_ADMIN_ROLE_NAME}")
        else:
            role = SysRole(
                code=SUPER_ADMIN_ROLE_CODE,
                name=SUPER_ADMIN_ROLE_NAME,
                description="拥有系统所有权限的根节点角色，仅限系统初始化时创建",
                is_active=True,
            )
            session.add(role)
            await session.flush()
            print(f"  [OK]   创建角色: {SUPER_ADMIN_ROLE_NAME} (id={role.id})")

        # ------------------------------------------------------------------
        # Step 3：绑定所有权限到超级管理员角色（幂等）
        # ------------------------------------------------------------------
        print("\n[STEP 3] 绑定权限到角色...")
        bind_count = 0
        for perm_id in perm_ids:
            existing_bind = await session.execute(
                select(sys_role_permission_table).where(
                    sys_role_permission_table.c.role_id == str(role.id),
                    sys_role_permission_table.c.permission_id == perm_id,
                )
            )
            if existing_bind.first():
                continue
            await session.execute(
                insert(sys_role_permission_table).values(
                    role_id=str(role.id),
                    permission_id=perm_id,
                )
            )
            bind_count += 1
        print(f"  [OK]   新增绑定 {bind_count} 个，总计 {len(perm_ids)} 个权限点绑定到 [{SUPER_ADMIN_ROLE_CODE}]")

        # ------------------------------------------------------------------
        # Step 4：创建超级管理员账号（幂等）
        # ------------------------------------------------------------------
        print(f"\n[STEP 4] 初始化管理员账号 [{SEED_USERNAME}]...")
        result = await session.execute(
            select(SysAdmin).where(SysAdmin.username == SEED_USERNAME)
        )
        admin = result.scalar_one_or_none()

        if admin:
            print(f"  [SKIP] 已存在: 管理员账号 [{SEED_USERNAME}]")
        else:
            hashed_pw = get_password_hash(SEED_PASSWORD)
            admin = SysAdmin(
                username=SEED_USERNAME,
                hashed_password=hashed_pw,
                real_name=SEED_REAL_NAME,
                is_active=True,
            )
            session.add(admin)
            await session.flush()
            print(f"  [OK]   创建管理员账号: {SEED_USERNAME} (id={admin.id})")

        # ------------------------------------------------------------------
        # Step 5：绑定账号到角色（幂等）
        # ------------------------------------------------------------------
        print("\n[STEP 5] 绑定账号到角色...")
        existing_admin_role = await session.execute(
            select(sys_admin_role_table).where(
                sys_admin_role_table.c.admin_id == str(admin.id),
                sys_admin_role_table.c.role_id == str(role.id),
            )
        )
        if existing_admin_role.first():
            print(f"  [SKIP] 已绑定: {SEED_USERNAME} <-> {SUPER_ADMIN_ROLE_NAME}")
        else:
            await session.execute(
                insert(sys_admin_role_table).values(
                    admin_id=str(admin.id),
                    role_id=str(role.id),
                )
            )
            print(f"  [OK]   绑定成功: {SEED_USERNAME} <-> {SUPER_ADMIN_ROLE_NAME}")

        # ------------------------------------------------------------------
        # Step 6：提交
        # ------------------------------------------------------------------
        await session.commit()
        print("\n" + "=" * 60)
        print("[DONE] 种子数据初始化完成")
        print("=" * 60)
        print(f"\n管理员登录信息:")
        print(f"  用户名: {SEED_USERNAME}")
        print(f"  密  码: {SEED_PASSWORD}")
        print(f"  权限数: {len(perm_ids)} 个")
        print(f"\n登录接口: POST /api/v1/admin/login")
        print(f"\n[WARN] 请在生产环境部署后立即修改默认密码!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed())
