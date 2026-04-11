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

  或者自定义管理员账号和密码：
  SEED_ADMIN_USERNAME=root SEED_ADMIN_PASSWORD=mypassword uv run python scripts/seed_admin.py

Author: jinmozhe
Created: 2026-04-12
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
# 基础权限点定义（用于系统初始化）
# 格式：(code, name, type)
# 后续可在后台管理界面扩充，这里只定义根节点和公共管理员权限
# ==============================================================================

INITIAL_PERMISSIONS: list[tuple[str, str, str]] = [
    # 顶级菜单入口
    ("dashboard:view",       "仪表盘",            "menu"),
    ("user:view",            "用户管理",           "menu"),
    ("user:create",          "新增用户",           "button"),
    ("user:edit",            "编辑用户",           "button"),
    ("user:ban",             "封禁/解封用户",      "button"),
    ("admin:view",           "管理员管理",         "menu"),
    ("admin:create",         "新增管理员",         "button"),
    ("admin:edit",           "编辑管理员",         "button"),
    ("role:view",            "角色管理",           "menu"),
    ("role:create",          "新增角色",           "button"),
    ("role:edit",            "编辑角色",           "button"),
    ("permission:view",      "权限管理",           "menu"),
    ("log:view",             "日志查看",           "menu"),
    ("order:view",           "订单查看",           "menu"),
    ("order:refund",         "订单退款",           "button"),
    ("finance:view",         "财务报表",           "menu"),
    ("finance:export",       "财务数据导出",       "button"),
]

# 超级管理员角色定义
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
        # ──────────────────────────────────────────────────────────
        # Step 1：初始化基础权限点（幂等：已存在则跳过）
        # ──────────────────────────────────────────────────────────
        print("\n[STEP 1] 初始化基础权限点 (sys_permissions)...")
        perm_ids: list[str] = []

        for code, name, ptype in INITIAL_PERMISSIONS:
            # 检查是否已经存在
            existing = await session.execute(
                select(SysPermission).where(SysPermission.code == code)
            )
            perm = existing.scalar_one_or_none()

            if perm:
                print(f"  [SKIP] 已存在: [{code}] {name}")
                perm_ids.append(str(perm.id))
            else:
                new_perm = SysPermission(code=code, name=name, type=ptype)
                session.add(new_perm)
                await session.flush()  # 获取自动生成的 id
                perm_ids.append(str(new_perm.id))
                print(f"  [OK]   创建权限点: [{code}] {name}")

        # ──────────────────────────────────────────────────────────
        # Step 2：创建超级管理员角色（幂等）
        # ──────────────────────────────────────────────────────────
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
                description="拥有系统所有权限的根节点角色，仅限系统初始化创建使用",
                is_active=True,
            )
            session.add(role)
            await session.flush()
            print(f"  [OK]   创建角色: {SUPER_ADMIN_ROLE_NAME} (id={role.id})")

        # ──────────────────────────────────────────────────────────
        # Step 3：绑定所有权限到超级管理员角色（幂等，已存在自动跳过）
        # ──────────────────────────────────────────────────────────
        print("\n[STEP 3] 绑定权限到角色...")
        for perm_id in perm_ids:
            # 检查绑定是否已存在
            existing_bind = await session.execute(
                select(sys_role_permission_table).where(
                    sys_role_permission_table.c.role_id == str(role.id),
                    sys_role_permission_table.c.permission_id == perm_id,
                )
            )
            if existing_bind.first():
                continue  # 已绑定，跳过

            await session.execute(
                insert(sys_role_permission_table).values(
                    role_id=str(role.id),
                    permission_id=perm_id,
                )
            )
        print(f"  [OK]   已确保 {len(perm_ids)} 个权限点绑定到 [{SUPER_ADMIN_ROLE_CODE}]")

        # ──────────────────────────────────────────────────────────
        # Step 4：创建超级管理员账号（幂等）
        # ──────────────────────────────────────────────────────────
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

        # ──────────────────────────────────────────────────────────
        # Step 5：绑定超级管理员账号到超级管理员角色
        # ──────────────────────────────────────────────────────────
        print("\n[STEP 5] 绑定账号到角色...")
        existing_admin_role = await session.execute(
            select(sys_admin_role_table).where(
                sys_admin_role_table.c.admin_id == str(admin.id),
                sys_admin_role_table.c.role_id == str(role.id),
            )
        )
        if existing_admin_role.first():
            print(f"  ⏭  跳过 (已绑定): {SEED_USERNAME} ↔ {SUPER_ADMIN_ROLE_NAME}")
        else:
            await session.execute(
                insert(sys_admin_role_table).values(
                    admin_id=str(admin.id),
                    role_id=str(role.id),
                )
            )
            print(f"  ✅ 绑定成功: {SEED_USERNAME} ↔ {SUPER_ADMIN_ROLE_NAME}")

        # ──────────────────────────────────────────────────────────
        # Step 6：一次性提交所有变更
        # ──────────────────────────────────────────────────────────
        await session.commit()
        print("\n" + "=" * 60)
        print("🎉 种子数据初始化完成！")
        print("=" * 60)
        print(f"\n🔑 管理员登录信息：")
        print(f"   用户名：{SEED_USERNAME}")
        print(f"   密   码：{SEED_PASSWORD}")
        print(f"\n📡 登录接口：POST /api/v1/admin/login")
        print(f"\n⚠️  请在生产环境部署后立即修改默认密码！")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed())
