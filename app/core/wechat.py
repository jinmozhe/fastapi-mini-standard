"""
File: app/core/wechat.py
Description: 微信小程序工具模块

职责：
1. code2session()       — 用 wx.login() 的 code 换取 openid + session_key
2. decrypt_phone_number() — AES-128-CBC 解密微信加密的手机号数据包

旁路逃生阀：
  如果 WECHAT_MINI_APP_ID 为空，模拟返回固定测试数据，方便本地开发。

Author: jinmozhe
Created: 2026-04-12
"""

import base64
import json
from dataclasses import dataclass

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import logger
from app.domains.auth.constants import AuthError


@dataclass
class WechatSessionResult:
    """code2session 返回结果"""
    openid: str
    session_key: str
    unionid: str | None = None


@dataclass
class WechatPhoneResult:
    """手机号解密结果"""
    phone_number: str        # 完整手机号（含国际区号，如 +8613800000000）
    pure_phone_number: str   # 纯手机号（不含区号，如 13800000000）
    country_code: str        # 国家区号（如 86）


async def code2session(js_code: str) -> WechatSessionResult:
    """
    用前端 wx.login() 返回的临时 code 向微信服务器换取 openid 和 session_key。

    微信官方接口文档：
    https://developers.weixin.qq.com/miniprogram/dev/OpenApiDoc/user-login/code2Session.html

    Args:
        js_code: 前端 wx.login() 返回的 code（有效期 5 分钟，一次性）

    Returns:
        WechatSessionResult: 包含 openid, session_key, unionid(可选)
    """
    # 旁路模式：未配置 AppID 时返回测试数据
    if not settings.WECHAT_MINI_APP_ID:
        logger.warning("[WeChat-Bypass] 小程序未配置 AppID，返回模拟数据")
        return WechatSessionResult(
            openid="test_openid_mock_12345",
            session_key="test_session_key_mock",
            unionid=None,
        )

    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.WECHAT_MINI_APP_ID,
        "secret": settings.WECHAT_MINI_APP_SECRET,
        "js_code": js_code,
        "grant_type": "authorization_code",
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params=params)
            data = response.json()

        # 微信错误码判断
        if "errcode" in data and data["errcode"] != 0:
            logger.error(f"[WeChat] code2session 失败: {data}")
            raise AppException(AuthError.WECHAT_AUTH_FAILED)

        return WechatSessionResult(
            openid=data["openid"],
            session_key=data["session_key"],
            unionid=data.get("unionid"),
        )

    except httpx.TimeoutException:
        logger.error("[WeChat] code2session 请求超时")
        raise AppException(AuthError.WECHAT_AUTH_FAILED)
    except AppException:
        raise
    except Exception as e:
        logger.error(f"[WeChat] code2session 异常: {e}")
        raise AppException(AuthError.WECHAT_AUTH_FAILED)


def decrypt_phone_number(
    session_key: str,
    encrypted_data: str,
    iv: str,
) -> WechatPhoneResult:
    """
    解密微信小程序 getPhoneNumber 返回的加密手机号数据。

    微信使用 AES-128-CBC 加密，密钥为 session_key 的 Base64 解码值，
    填充方式为 PKCS#7。

    Args:
        session_key: code2session 获取的会话密钥
        encrypted_data: wx.getPhoneNumber 返回的加密数据
        iv: 加密初始向量

    Returns:
        WechatPhoneResult: 解密后的手机号信息
    """
    # 旁路模式
    if not settings.WECHAT_MINI_APP_ID:
        logger.warning("[WeChat-Bypass] 小程序未配置，返回模拟手机号")
        return WechatPhoneResult(
            phone_number="+8613800000000",
            pure_phone_number="13800000000",
            country_code="86",
        )

    try:
        # Base64 解码
        aes_key = base64.b64decode(session_key)
        aes_iv = base64.b64decode(iv)
        cipher_text = base64.b64decode(encrypted_data)

        # AES-128-CBC 解密
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_iv))
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(cipher_text) + decryptor.finalize()

        # PKCS7 去填充
        unpadder = PKCS7(128).unpadder()
        plain_data = unpadder.update(padded_data) + unpadder.finalize()

        # 解析明文 JSON
        phone_info = json.loads(plain_data.decode("utf-8"))

        return WechatPhoneResult(
            phone_number=phone_info.get("phoneNumber", ""),
            pure_phone_number=phone_info.get("purePhoneNumber", ""),
            country_code=phone_info.get("countryCode", "86"),
        )

    except Exception as e:
        logger.error(f"[WeChat] 手机号解密失败: {e}")
        raise AppException(AuthError.WECHAT_DECRYPT_FAILED)
