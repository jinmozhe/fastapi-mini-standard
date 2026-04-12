"""
File: app/core/sms.py
Description: 短信验证码核心组件 (腾讯云 SMS + Redis)

职责：
1. send_sms_code()  — 生成验证码 → 存入 Redis → 调用腾讯云发送
2. verify_sms_code() — 从 Redis 取出验证码比对 → 验证通过后立即删除
3. 防刷机制: 同一手机号 60 秒内只允许发送一次
4. 旁路逃生阀: SMS_ENABLE=False 时不实际发送，验证码固定 888888

Author: jinmozhe
Created: 2026-04-12
"""

import random
import string

import httpx
from redis.asyncio import Redis

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import logger
from app.domains.auth.constants import AuthError


def _generate_code(length: int = 6) -> str:
    """生成指定位数的纯数字验证码"""
    return "".join(random.choices(string.digits, k=length))


# Redis Key 命名规范
def _code_key(phone_code: str, mobile: str) -> str:
    """验证码存储 Key"""
    return f"sms_code:{phone_code}:{mobile}"


def _lock_key(phone_code: str, mobile: str) -> str:
    """发送冷却锁 Key"""
    return f"sms_lock:{phone_code}:{mobile}"


async def send_sms_code(
    redis: Redis,
    phone_code: str,
    mobile: str,
    sms_type: str = "login",
    ip_address: str | None = None,
) -> str:
    """
    发送短信验证码。

    流程：
    1. 检查 60 秒冷却锁 (防刷)
    2. 生成随机验证码
    3. 存入 Redis（TTL = SMS_CODE_EXPIRE_SECONDS）
    4. 设置 60 秒冷却锁
    5. 调用腾讯云 SMS API 发送

    Returns:
        生成的验证码（用于日志或测试环境返回）
    """
    # 1. 防刷：检查冷却锁
    lock = _lock_key(phone_code, mobile)
    if await redis.exists(lock):
        raise AppException(AuthError.SMS_SEND_TOO_FREQUENT)

    # 2. 生成验证码
    if not settings.SMS_ENABLE:
        # 旁路模式：固定验证码便于开发调试
        code = "8" * settings.SMS_CODE_LENGTH
        logger.info(
            f"[SMS-Bypass] 短信未启用，使用固定验证码: {code} → {phone_code}{mobile}"
        )
    else:
        code = _generate_code(settings.SMS_CODE_LENGTH)

    # 3. 存入 Redis
    code_key = _code_key(phone_code, mobile)
    await redis.setex(code_key, settings.SMS_CODE_EXPIRE_SECONDS, code)

    # 4. 设置冷却锁
    await redis.setex(lock, settings.SMS_SEND_INTERVAL, "1")

    # 5. 实际发送短信
    if settings.SMS_ENABLE:
        await _send_tencent_sms(phone_code, mobile, code, sms_type)

    return code


async def verify_sms_code(
    redis: Redis,
    phone_code: str,
    mobile: str,
    code: str,
) -> bool:
    """
    验证短信验证码。

    流程：
    1. 检查是否已被锁定（5 次错误后自动锁定）
    2. 从 Redis 读取存储的验证码
    3. 比对是否一致
    4. 错误时累加计数器，达到上限就删除验证码
    5. 验证通过后立即删除（防重放）

    Raises:
        AppException: 验证码错误或已过期
    """
    code_key = _code_key(phone_code, mobile)
    attempts_key = f"sms_attempts:{phone_code}:{mobile}"
    max_attempts = 5

    # 1. 检查错误次数是否已达上限
    attempts_raw = await redis.get(attempts_key)
    if attempts_raw:
        attempts = int(attempts_raw if isinstance(attempts_raw, str) else attempts_raw.decode())
        if attempts >= max_attempts:
            # 已超限，直接清除验证码和计数器
            await redis.delete(code_key, attempts_key)
            raise AppException(AuthError.SMS_CODE_INVALID)

    stored_code = await redis.get(code_key)

    if not stored_code:
        raise AppException(AuthError.SMS_CODE_INVALID)

    # Redis 返回 bytes，需要 decode
    stored_str = stored_code if isinstance(stored_code, str) else stored_code.decode()

    if stored_str != code:
        # 错误：累加计数器（与验证码同生命周期）
        await redis.incr(attempts_key)
        # 设置计数器过期时间与验证码一致
        ttl = await redis.ttl(code_key)
        if ttl > 0:
            await redis.expire(attempts_key, ttl)
        raise AppException(AuthError.SMS_CODE_INVALID)

    # 验证通过，立即删除验证码和计数器（一次性使用）
    await redis.delete(code_key, attempts_key)
    return True


async def _send_tencent_sms(
    phone_code: str,
    mobile: str,
    code: str,
    sms_type: str,
) -> None:
    """
    调用腾讯云 SMS API 发送短信。

    架构说明：
    腾讯云 SMS 的 v2021-01-11 版本 API 通过 HTTPS POST 调用，
    需要 TC3-HMAC-SHA256 签名。本方法使用 HttpX 直接通讯，
    不依赖官方 SDK。

    TODO: 上线前需要实现完整的 TC3 签名算法。
    """
    full_mobile = f"{phone_code}{mobile}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # === 以下为生产环境正式启用时的参考实现 ===
            #
            # 1. 构造请求 Body
            # payload = {
            #     "SmsSdkAppId": settings.SMS_APP_ID,
            #     "SignName": settings.SMS_SIGN_NAME,
            #     "TemplateId": settings.SMS_TEMPLATE_LOGIN,
            #     "TemplateParamSet": [code, str(settings.SMS_CODE_EXPIRE_SECONDS // 60)],
            #     "PhoneNumberSet": [full_mobile],
            # }
            #
            # 2. 计算 TC3-HMAC-SHA256 签名 Header
            # headers = _build_tc3_headers(payload)
            #
            # 3. 发送请求
            # response = await client.post(
            #     "https://sms.tencentcloudapi.com/",
            #     json=payload,
            #     headers=headers,
            # )
            # data = response.json()
            #
            # 4. 判断结果
            # send_status = data.get("Response", {}).get("SendStatusSet", [{}])[0]
            # if send_status.get("Code") != "Ok":
            #     raise AppException(AuthError.SMS_SEND_FAILED)

            logger.info(
                f"[SMS-Tencent] 短信发送骨架已触发: {full_mobile}, "
                f"type={sms_type}, code={code}"
            )

    except httpx.TimeoutException:
        # 降级策略 (Fail-Open)：短信网关超时时不阻塞主流程
        # 验证码已存入 Redis，用户可以重试发送
        logger.error(f"[SMS-Tencent] 发送超时: {full_mobile}")
        raise AppException(AuthError.SMS_SEND_FAILED)
    except AppException:
        raise
    except Exception as e:
        logger.error(f"[SMS-Tencent] 发送异常: {e}")
        raise AppException(AuthError.SMS_SEND_FAILED)
