"""
File: app/domains/user_levels/constants.py
Description: 用户等级领域常量定义 (错误码 + 成功提示)
Namespace: user_level.*

Author: jinmozhe
Created: 2026-04-12
"""

from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

from app.core.error_code import BaseErrorCode


class UserLevelError(BaseErrorCode):
    """
    用户等级领域错误码定义
    Tuple Structure: (HTTP_Status, Code_String, Default_Message)
    """

    # 等级不存在
    LEVEL_NOT_FOUND = (HTTP_404_NOT_FOUND, "user_level.not_found", "会员等级不存在")

    # 等级名称重复
    LEVEL_NAME_EXIST = (HTTP_409_CONFLICT, "user_level.name_exist", "该等级名称已存在")

    # 等级权重重复
    LEVEL_RANK_EXIST = (HTTP_409_CONFLICT, "user_level.rank_exist", "该等级权重已被占用")

    # 存在关联用户，无法删除
    LEVEL_HAS_USERS = (HTTP_409_CONFLICT, "user_level.has_users", "该等级下存在关联用户，无法删除")

    # 用户等级档案不存在
    PROFILE_NOT_FOUND = (HTTP_404_NOT_FOUND, "user_level.profile_not_found", "该用户尚未建立等级档案")

    # 无效的升级规则 JSON 结构
    INVALID_UPGRADE_RULES = (HTTP_400_BAD_REQUEST, "user_level.invalid_upgrade_rules", "升级规则格式无效")

    # 权限不足
    PERMISSION_DENIED = (HTTP_403_FORBIDDEN, "user_level.permission_denied", "权限不足，您无法执行该操作")


class UserLevelMsg:
    """
    用户等级领域成功提示文案
    """

    # B端管理操作
    LEVEL_CREATED = "等级创建成功"
    LEVEL_UPDATED = "等级更新成功"
    LEVEL_DELETED = "等级删除成功"
    LEVEL_LIST = "获取等级列表成功"
    LEVEL_DETAIL = "获取等级详情成功"

    # 人工干预
    OVERRIDE_SUCCESS = "已手工指定用户等级"
    RELEASE_SUCCESS = "已解除人工锁定，恢复自动计算"

    # C端查询
    C_LEVEL_LIST = "获取会员等级体系成功"
