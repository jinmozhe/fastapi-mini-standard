"""
File: app/domains/admin/schemas.py
Description: B端管理员领域数据模型 (Pydantic Schema)

作为 B 端登录 / 权限树查询时的请求与响应契约。

Author: jinmozhe
Created: 2026-04-12
"""

from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 1. 请求模型 (Request Schemas)
# ==============================================================================


class AdminLoginRequest(BaseModel):
    """管理员登录请求"""

    username: str = Field(..., min_length=3, max_length=50, description="管理员后台登录名")
    password: str = Field(..., min_length=8, max_length=128, description="登录密码")


class AdminRefreshRequest(BaseModel):
    """管理员令牌刷新请求"""

    refresh_token: str = Field(..., description="当前持有的 Refresh Token")


class AdminLogoutRequest(BaseModel):
    """管理员登出请求"""

    refresh_token: str = Field(..., description="需要主动销毁的 Refresh Token")


# ==============================================================================
# 2. 响应模型 (Response Schemas)
# ==============================================================================


class AdminToken(BaseModel):
    """管理员双Token响应"""

    access_token: str = Field(..., description="短效 Access Token (Bearer Header 携带)")
    refresh_token: str = Field(..., description="长效 Refresh Token (用于续期)")
    token_type: str = Field(default="bearer", description="Token 类型")


class PermissionOut(BaseModel):
    """权限点输出模型"""

    model_config = ConfigDict(from_attributes=True)

    code: str = Field(..., description="权限标识串 (如: order:refund)")
    name: str = Field(..., description="显示名称 (如: 订单退款)")
    type: str = Field(..., description="类型: menu|button|api")
    parent_id: str | None = Field(None, description="父节点ID (用于构建菜单树)")


class RoleOut(BaseModel):
    """角色输出模型 (含权限列表)"""

    model_config = ConfigDict(from_attributes=True)

    code: str = Field(..., description="角色编码 (如: FINANCE_MANAGER)")
    name: str = Field(..., description="角色显示名称")
    permissions: list[PermissionOut] = Field(default_factory=list, description="该角色拥有的权限点列表")


class AdminMe(BaseModel):
    """
    管理员自身信息 + 权限树输出。
    这是 React 等前端框架最关键的数据接口：
    用于动态渲染侧边栏菜单和控制按钮的显示与隐藏。
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="管理员 ID")
    username: str = Field(..., description="登录用户名")
    real_name: str | None = Field(None, description="内部真名/花名")
    is_active: bool = Field(..., description="账号是否激活")
    roles: list[RoleOut] = Field(default_factory=list, description="角色列表")

    @property
    def permission_codes(self) -> list[str]:
        """
        提取当前管理员所有去重权限码的扁平列表。
        方便前端直接检查 permissions.includes("order:refund")
        """
        codes = set()
        for role in self.roles:
            for perm in role.permissions:
                codes.add(perm.code)
        return list(codes)
