"""
File: app/core/config.py
Description: 全局应用配置管理（使用 pydantic-settings）

所有配置值通过 .env 文件加载。
本模块负责：
1. 校验环境变量类型
2. 解析复杂类型（如 CORS 列表）
3. 组装数据库 DSN（确保使用 postgresql+asyncpg 协议）
4. 定义 Redis 连接与 JWT 安全参数
5. 运行时强制校验必填项，确保应用在配置缺失时快速失败

Author: jinmozhe
Created: 2025-11-24
"""

from typing import Literal

from pydantic import AnyHttpUrl, model_validator
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置对象（唯一真实来源）"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=True,
    )

    # --------------------------------------------------------------------------
    # 1. General (通用)
    # --------------------------------------------------------------------------
    PROJECT_NAME: str = "FastAPI V3.0 Project"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: Literal["local", "dev", "prod"] = "local"
    DEBUG: bool = False

    # 密钥 (生产环境强制要求高强度随机串)
    # 用于 Session 签名和 JWT 加密
    SECRET_KEY: str | None = None

    # CORS 配置（Pydantic 会自动解析 JSON 字符串列表）
    BACKEND_CORS_ORIGINS: list[AnyHttpUrl] = []

    # --------------------------------------------------------------------------
    # 2. Database (PostgreSQL)
    # --------------------------------------------------------------------------
    POSTGRES_SERVER: str | None = None
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_DB: str | None = None

    # 连接池配置 (Pool Settings)
    DB_POOL_SIZE: int = 20  # 连接池基准大小
    DB_MAX_OVERFLOW: int = 10  # 允许超出基准的额外连接数
    DB_POOL_PRE_PING: bool = True  # 每次获取连接前是否自动 ping
    DB_POOL_TIMEOUT: int = 30  # 连接获取超时（秒）
    DB_POOL_RECYCLE: int = 1800  # 连接回收时间（秒），防止连接过期

    # 完整 DSN 覆盖（可选）
    SQLALCHEMY_DATABASE_URI: str | None = None

    # --------------------------------------------------------------------------
    # 3. Logging (Loguru)
    # --------------------------------------------------------------------------
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_JSON_FORMAT: bool = False  # 是否输出 JSON 格式
    LOG_FILE_ENABLED: bool = False  # 是否启用文件日志
    LOG_DIR: str = "logs"  # 日志文件目录
    LOG_ROTATION: str = "1 hour"  # 轮转策略
    LOG_RETENTION: str = "7 days"  # 保留时间
    LOG_COMPRESSION: str = "zip"  # 压缩格式
    LOG_DIAGNOSE: bool = True  # 是否启用诊断信息（生产环境建议 False）

    # --------------------------------------------------------------------------
    # 4. Redis Settings (缓存与 Token 存储)
    # --------------------------------------------------------------------------
    # 默认连接本地，生产环境请在 .env 中覆盖
    REDIS_URL: str = "redis://localhost:6379/0"

    # --------------------------------------------------------------------------
    # 5. Security & Authentication (JWT)
    # --------------------------------------------------------------------------
    # Access Token 有效期 (分钟) - 短效，无状态
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Refresh Token 有效期 (天) - 长效，存储于 Redis
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # JWT 签名算法 (推荐使用 HS256)
    ALGORITHM: str = "HS256"

    # --------------------------------------------------------------------------
    # 6. CAPTCHA Settings (验证码防刷与人机验证)
    # --------------------------------------------------------------------------
    # 安全逃生舱：在开发测试环境或出问题时，可随时设为 False 绕过所有验证码校验
    CAPTCHA_ENABLE: bool = False
    # 支持的提供商：当前默认实现腾讯云骨架适配
    CAPTCHA_PROVIDER: Literal["tencent", "aliyun"] = "tencent"
    CAPTCHA_SECRET_ID: str = ""
    CAPTCHA_SECRET_KEY: str = ""
    CAPTCHA_APP_ID: str = ""

    # --------------------------------------------------------------------------
    # 7. SMS Settings (腾讯云短信服务)
    # --------------------------------------------------------------------------
    # 总闸开关：开发环境关闭后验证码固定为 888888，不会实际发送短信
    SMS_ENABLE: bool = False
    # 腾讯云 API 凭证
    SMS_SECRET_ID: str = ""
    SMS_SECRET_KEY: str = ""
    # 短信应用 SDK AppID（腾讯云短信控制台获取）
    SMS_APP_ID: str = ""
    # 短信签名内容（需在腾讯云审核通过）
    SMS_SIGN_NAME: str = ""
    # 登录验证码模板 ID
    SMS_TEMPLATE_LOGIN: str = ""
    # 验证码有效期（秒），默认 5 分钟
    SMS_CODE_EXPIRE_SECONDS: int = 300
    # 验证码位数
    SMS_CODE_LENGTH: int = 6
    # 同一手机号发送冷却时间（秒），防刷
    SMS_SEND_INTERVAL: int = 60

    # --------------------------------------------------------------------------
    # 8. WeChat Settings (微信生态)
    # --------------------------------------------------------------------------
    # 小程序
    WECHAT_MINI_APP_ID: str = ""
    WECHAT_MINI_APP_SECRET: str = ""
    # 开放平台 (网页扫码登录)
    WECHAT_OPEN_APP_ID: str = ""
    WECHAT_OPEN_APP_SECRET: str = ""

    # --------------------------------------------------------------------------
    # Properties (便捷属性)
    # --------------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.ENVIRONMENT == "prod"

    @property
    def is_debug(self) -> bool:
        """是否启用调试模式（仅在非生产环境有效）"""
        return self.DEBUG and not self.is_production

    # --------------------------------------------------------------------------
    # Validators
    # --------------------------------------------------------------------------
    @model_validator(mode="after")
    def _validate_and_build_db_uri(self) -> "Settings":
        """验证必填项并构建数据库连接串。"""
        # 1. 校验 SECRET_KEY
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY 必须在 .env 中设置")

        # 生产环境强制校验密钥强度
        if self.ENVIRONMENT == "prod" and len(self.SECRET_KEY) < 32:
            raise ValueError("生产环境 SECRET_KEY 长度必须 >= 32 字符")

        # 2. 如果 env 直接提供了 DSN，则优先使用
        if self.SQLALCHEMY_DATABASE_URI:
            return self

        # 3. 否则检查 POSTGRES_* 字段是否齐全
        missing_fields: list[str] = []
        required_pg_fields = [
            "POSTGRES_SERVER",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
        ]

        for field in required_pg_fields:
            if not getattr(self, field):
                missing_fields.append(field)

        if missing_fields:
            raise ValueError(
                f"缺少数据库环境变量，无法构建 DSN: {', '.join(missing_fields)}"
            )

        # 4. 自动组装 DSN
        self.SQLALCHEMY_DATABASE_URI = str(
            MultiHostUrl.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,  # type: ignore[arg-type]
                password=self.POSTGRES_PASSWORD,  # type: ignore[arg-type]
                host=self.POSTGRES_SERVER,  # type: ignore[arg-type]
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,  # type: ignore[arg-type]
            )
        )

        return self


# 单例配置对象
# 配置加载失败时，Pydantic 会抛出 ValidationError，包含详细错误信息
settings = Settings()
