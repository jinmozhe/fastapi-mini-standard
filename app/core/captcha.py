"""
File: app/core/captcha.py
Description: 防刷行为验证码校验核心组件 (纯 HttpX 方案骨架)

Author: jinmozhe
Created: 2026-04-12
"""

import httpx

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import logger
from app.domains.auth.constants import AuthError


async def verify_captcha_async(ticket: str, rand_str: str, client_ip: str) -> bool:
    """
    请求云服务商验证前端传入的行为验证码。
    
    :param ticket: 前端滑动验证成功后返回的 token
    :param rand_str: 验证过程中特有的随机串参数 (有些云厂例如腾讯云需要)
    :param client_ip: 用户请求发起 IP，辅助做风控判定
    """
    # 【旁路逃生阀】: 如果没有开启总闸，安全放过，让本地开发和未准备好 Key 的项目顺畅运行代码
    if not settings.CAPTCHA_ENABLE:
        return True

    if not ticket:
        logger.warning(f"Captcha verification failed: empty ticket from IP {client_ip}")
        raise AppException(AuthError.CAPTCHA_ERROR)

    # 路由到云端检查器
    if settings.CAPTCHA_PROVIDER == "tencent":
        return await _verify_tencent_captcha(ticket, rand_str, client_ip)
    
    # 默认兜底
    return False


async def _verify_tencent_captcha(ticket: str, rand_str: str, client_ip: str) -> bool:
    """
    对接腾讯云/阿里云的底层通讯核心骨架。
    
    注意：在纯后端项目中，云厂商的安全审核大多是发送一段标准的 HTTP 请求。
    为了彻底抛弃臃肿的官方 SDK，建议在此处阅读云平台官方 API 文档，
    使用 HttpX 给目标网关发包核验。
    """
    
    # 获取环境变量里面的密钥材料
    app_id = settings.CAPTCHA_APP_ID
    app_secret = settings.CAPTCHA_SECRET_KEY
    
    # (此部分为 HttpX 通讯架构演示)
    # 因为很多云平台（如腾讯云 v3）需要对请求进行 SHA256 甚至 HMAC_SHA256 签名计算，
    # 真正的生产系统你需要写几行加解密拼装 Header。
    
    _payload = {
        "Action": "DescribeCaptchaResult",
        "CaptchaType": 9,
        "Ticket": ticket,
        "UserIp": client_ip,
        "Randstr": rand_str,
        "CaptchaAppId": int(app_id) if app_id.isdigit() else 0,
        "AppSecretKey": app_secret, 
    }
    
    try:
        # 为了不拖累系统性能，对验证码的校验设置极为苛刻的超时时间（比如3秒）
        async with httpx.AsyncClient(timeout=3.0) as _client:
            # === 下方为将来正式启用时的参考写法解说 ===
            
            # response = await client.post("https://captcha.tencentcloudapi.com/", json=payload, headers={...签名字段...})
            # data = response.json()
            #
            # # 判断云厂的鉴权通过标识：
            # if data.get("Response", {}).get("CaptchaCode") == 1:
            #     return True
            # else:
            #     logger.opt(colors=True).error(f"Captcha failed: <red>{data}</red>")
            #     raise AppException(AuthError.CAPTCHA_ERROR)
            
            logger.info("腾讯云动作验证骨架被成功唤起...")
            return True
            
    except httpx.TimeoutException:
        # 【架构决策：降级机制 (Fail-Open)】
        # 如果因为阿里云大面积故障导致请求验证码超时，宁可短时间放行所有请求，
        # 也不要让平台陷入所有人因为验证码发不出去而 100% 无法登录的瘫痪惨剧。
        logger.error("Captcha service timeout, failed open globally.")
        return True
    
    except Exception as e:
        if isinstance(e, AppException):
            raise e
        logger.error(f"Captcha unexpected error: {e}")
        return False
