"""
File: app/core/rate_limit.py
Description: 原生基于 Redis 的极简滑动限流器依赖 (Rate Limiter)

Author: jinmozhe
Created: 2026-04-12
"""

from fastapi import Request
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.core.exceptions import AppException
from app.core.redis import redis_client


class RateLimiter:
    """
    极度轻量的 API 限流拦截器。
    
    用法：
    @router.post("/login", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
    """

    def __init__(self, times: int = 5, seconds: int = 60):
        """
        :param times: 允许访问最大次数
        :param seconds: 时间窗口 (秒)
        """
        self.times = times
        self.seconds = seconds

    async def __call__(self, request: Request):
        # 获取真实客户端 IP (如果经过 SLB/代理，需在其他中间件中提取 x-forwarded-for 赋给 state)
        client_ip = getattr(request.state, "real_ip", None)
        if not client_ip:
            client_ip = request.client.host if request.client else "127.0.0.1"

        # 根据接口路径和 IP 构造限流桶
        key = f"rate_limit:{request.url.path}:{client_ip}"

        try:
            # 原子操作自增
            current_hits = await redis_client.incr(key)
            if current_hits == 1:
                # 首次访问，设置过期销毁时间（建立滑动窗口）
                await redis_client.expire(key, self.seconds)
                
            if current_hits > self.times:
                raise AppException(
                    HTTP_429_TOO_MANY_REQUESTS,
                    message="请求过于频繁，请冷静一下稍后再试",
                )
        except Exception as e:
            # 如果是鉴权拦截的异常，正常抛出
            if isinstance(e, AppException):
                raise e
            # 如果是 Redis 崩了抛出异常，触发熔断降级（Fail-Open），不影响真实业务
            pass
