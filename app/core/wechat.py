"""
File: app/core/wechat.py
Description: 微信工具模块 (小程序 + 开放平台)

职责：
1. code2session()         — 小程序: wx.login() 的 code 换取 openid + session_key
2. decrypt_phone_number()  — 小程序: AES-128-CBC 解密微信加密的手机号数据包
3. code2access_token()     — 开放平台: 网页扫码授权 code 换取 openid + access_token

旁路逃生阀：
  如果对应的 AppID 为空，模拟返回固定测试数据，方便本地开发。

Author: jinmozhe
Created: 2026-04-12
Updated: 2026-04-12 (新增开放平台 OAuth 支持)
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
    """code2session 返回结果 (小程序)"""
    openid: str
    session_key: str
    unionid: str | None = None


@dataclass
class WechatPhoneResult:
    """手机号解密结果"""
    phone_number: str        # 完整手机号（含国际区号，如 +8613800000000）
    pure_phone_number: str   # 纯手机号（不含区号，如 13800000000）
    country_code: str        # 国家区号（如 86）


@dataclass
class WechatOAuthResult:
    """开放平台网页授权结果"""
    openid: str
    access_token: str
    unionid: str | None = None
    nickname: str | None = None
    avatar: str | None = None


# ==============================================================================
# 小程序相关
# ==============================================================================


async def code2session(js_code: str) -> WechatSessionResult:
    """
    用前端 wx.login() 返回的临时 code 向微信服务器换取 openid 和 session_key。

    微信官方接口文档：
    https://developers.weixin.qq.com/miniprogram/dev/OpenApiDoc/user-login/code2Session.html
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
    微信使用 AES-128-CBC 加密，密钥为 session_key 的 Base64 解码值。
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
        aes_key = base64.b64decode(session_key)
        aes_iv = base64.b64decode(iv)
        cipher_text = base64.b64decode(encrypted_data)

        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_iv))
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(cipher_text) + decryptor.finalize()

        unpadder = PKCS7(128).unpadder()
        plain_data = unpadder.update(padded_data) + unpadder.finalize()

        phone_info = json.loads(plain_data.decode("utf-8"))

        return WechatPhoneResult(
            phone_number=phone_info.get("phoneNumber", ""),
            pure_phone_number=phone_info.get("purePhoneNumber", ""),
            country_code=phone_info.get("countryCode", "86"),
        )

    except Exception as e:
        logger.error(f"[WeChat] 手机号解密失败: {e}")
        raise AppException(AuthError.WECHAT_DECRYPT_FAILED)


# ==============================================================================
# 开放平台：网页端微信扫码登录
# ==============================================================================


async def code2access_token(code: str) -> WechatOAuthResult:
    """
    网页端微信扫码授权：用 code 换取 access_token + openid。

    流程：
    1. 前端引导用户跳转微信扫码页面（带 redirect_uri）
    2. 用户扫码授权后，微信回调 redirect_uri 并附带 code
    3. 后端用 code 向微信换取 access_token + openid
    4. (可选) 用 access_token 拉取用户信息（昵称、头像）

    文档：https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/Wechat_Login.html
    """
    # 旁路模式
    if not settings.WECHAT_OPEN_APP_ID:
        logger.warning("[WeChat-Bypass] 开放平台未配置 AppID，返回模拟数据")
        return WechatOAuthResult(
            openid="test_web_openid_mock_67890",
            access_token="test_access_token_mock",
            unionid="test_unionid_mock",
            nickname="测试用户",
            avatar=None,
        )

    # Step 1: code 换 access_token + openid
    token_url = "https://api.weixin.qq.com/sns/oauth2/access_token"
    params = {
        "appid": settings.WECHAT_OPEN_APP_ID,
        "secret": settings.WECHAT_OPEN_APP_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(token_url, params=params)
            data = resp.json()

            if "errcode" in data and data["errcode"] != 0:
                logger.error(f"[WeChat-Open] code 换 token 失败: {data}")
                raise AppException(AuthError.WECHAT_AUTH_FAILED)

            openid = data["openid"]
            access_token = data["access_token"]
            unionid = data.get("unionid")

            # Step 2: 拉取用户基础信息（昵称、头像）
            nickname = None
            avatar = None
            try:
                userinfo_url = "https://api.weixin.qq.com/sns/userinfo"
                info_resp = await client.get(
                    userinfo_url,
                    params={"access_token": access_token, "openid": openid},
                )
                info_data = info_resp.json()
                if info_data.get("errcode") is None or info_data.get("errcode") == 0:
                    nickname = info_data.get("nickname")
                    avatar = info_data.get("headimgurl")
                    if not unionid:
                        unionid = info_data.get("unionid")
            except Exception as e:
                logger.warning(f"[WeChat-Open] 拉取用户信息失败 (不影响主流程): {e}")

            return WechatOAuthResult(
                openid=openid,
                access_token=access_token,
                unionid=unionid,
                nickname=nickname,
                avatar=avatar,
            )

    except httpx.TimeoutException:
        logger.error("[WeChat-Open] 请求超时")
        raise AppException(AuthError.WECHAT_AUTH_FAILED)
    except AppException:
        raise
    except Exception as e:
        logger.error(f"[WeChat-Open] 异常: {e}")
        raise AppException(AuthError.WECHAT_AUTH_FAILED)
