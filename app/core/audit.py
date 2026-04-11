"""
File: app/core/audit.py
Description: B端管理员全量操作审计日志中间件 (AuditLogMiddleware)

拦截所有 /admin/ 路径下的任何请求（含 GET、POST、DELETE 等所有方法），
将操作者身份、请求参数快照、响应状态码存入 sys_audit_logs 表，形成完整操作轨迹。

设计原则：
1. 全量覆盖：/admin/ 下的所有请求都记录，任何人任何操作一条不漏。
2. 旁路提交：独立开启 DB Session 写日志，与主请求事务完全解耦。
3. Fail-Open：写日志失败绝对不影响业务响应，只输出 error 日志。
4. 请求体重建：读取 Body 后重新注入 receive，保障后续路由正常解析。
5. 脱敏保护：password/token 等敏感字段自动替换为 '***' 再落库。

Author: jinmozhe
Created: 2026-04-12
"""

import json
from collections.abc import Awaitable, Callable

import jwt
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import logger
from app.db.models.log import AuditLog
from app.db.session import AsyncSessionLocal

# 请求体快照的最大字节数（防止超大 Body 撑爆内存）
MAX_BODY_SIZE: int = 8 * 1024  # 8 KB


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    B端管理员全量操作审计日志中间件。

    工作流程：
    请求进入 → 判断路径是否含 /admin/
           ↓ 是（任何方法均拦截）
    提取 JWT admin_id（手动解析，不走 FastAPI 依赖注入）
           ↓
    读取请求参数：
      - 写请求(POST/PUT/PATCH/DELETE)：读取 Body JSON 快照
      - 读请求(GET/HEAD)：读取 Query String 参数
           ↓
    重建请求体 receive 流（保障路由层能正常解析 Body）
           ↓
    执行主请求（call_next）
           ↓
    获取响应状态码
           ↓
    异步旁路写入 AuditLog（独立 Session，Fail-Open）
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        method = request.method

        # 只拦截 /admin/ 路径，对 C端和其他路径完全放行
        if "/admin/" not in path:
            return await call_next(request)

        # ──────────────────────────────────────────────
        # 1. 提取管理员身份（手动解码 JWT，不依赖 DI）
        # ──────────────────────────────────────────────
        admin_id: str | None = None
        try:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                payload = jwt.decode(
                    token,
                    settings.SECRET_KEY,  # type: ignore[arg-type]
                    algorithms=[settings.ALGORITHM],
                    options={"verify_aud": False, "verify_exp": False},
                )
                if payload.get("aud") == "backend":
                    admin_id = payload.get("sub")
        except Exception:
            # JWT 解析失败不影响业务，admin_id 保持 None 继续记录匿名操作
            pass

        # ──────────────────────────────────────────────
        # 2. 提取请求参数快照
        # ──────────────────────────────────────────────
        payload_snapshot: dict | None = None
        body_bytes: bytes = b""

        if method in ("POST", "PUT", "PATCH", "DELETE"):
            # 写操作：读取请求体 JSON 快照
            try:
                body_bytes = await request.body()

                # 重建 receive 流，保障路由层 Pydantic 正常解析 Body
                async def receive():
                    return {"type": "http.request", "body": body_bytes, "more_body": False}

                request._receive = receive  # type: ignore[attr-defined]

                if body_bytes:
                    truncated = body_bytes[:MAX_BODY_SIZE]
                    try:
                        payload_snapshot = json.loads(truncated)
                        _mask_sensitive_fields(payload_snapshot)
                    except (json.JSONDecodeError, ValueError):
                        payload_snapshot = {"_raw": truncated.decode("utf-8", errors="replace")}
            except Exception as e:
                logger.warning(f"AuditLogMiddleware: Failed to read body: {e}")

        else:
            # 读操作（GET/HEAD 等）：记录 Query String 参数
            query_params = dict(request.query_params)
            if query_params:
                payload_snapshot = query_params

        # ──────────────────────────────────────────────
        # 3. 执行主请求（任何情况下都不阻塞）
        # ──────────────────────────────────────────────
        response = await call_next(request)
        status_code: int = response.status_code

        # ──────────────────────────────────────────────
        # 4. 旁路写入审计日志（独立 Session，Fail-Open）
        # ──────────────────────────────────────────────
        module, action = _extract_module_action(path, method)
        ip_address = request.headers.get(
            "X-Forwarded-For",
            request.client.host if request.client else None,
        )

        try:
            async with AsyncSessionLocal() as session:
                log = AuditLog(
                    actor_type="admin",
                    actor_id=admin_id,
                    module=module,
                    action=action,
                    endpoint=str(request.url.path),
                    method=method,
                    ip_address=ip_address,
                    request_payload=payload_snapshot,
                    response_status=status_code,
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            # Fail-Open：写日志失败不影响业务，只记录错误
            logger.error(f"AuditLogMiddleware: Failed to write audit log: {e}")

        return response


# ==============================================================================
# 私有辅助函数
# ==============================================================================


def _mask_sensitive_fields(data: dict) -> None:
    """
    原地脱敏处理：将请求体中的敏感字段值替换为 '***'。
    防止明文密码、Token 等高敏信息落入 AuditLog JSONB 字段。
    """
    SENSITIVE_KEYS: frozenset[str] = frozenset({
        "password", "old_password", "new_password", "confirm_password",
        "token", "access_token", "refresh_token", "secret", "secret_key",
        "card_number", "cvv", "id_card", "identity_card",
    })
    for key in list(data.keys()):
        if key.lower() in SENSITIVE_KEYS:
            data[key] = "***"
        elif isinstance(data[key], dict):
            _mask_sensitive_fields(data[key])


def _extract_module_action(path: str, method: str) -> tuple[str, str]:
    """
    从请求路径和 HTTP 方法推断 module 和 action 字段。

    示例：
      POST   /api/v1/admin/products          → ("products", "create")
      GET    /api/v1/admin/products          → ("products", "list")
      GET    /api/v1/admin/me                → ("admin", "me")
      POST   /api/v1/admin/login             → ("admin", "login")
      DELETE /api/v1/admin/products/123      → ("products", "delete")
      PUT    /api/v1/admin/orders/456/refund → ("orders", "refund")
    """
    METHOD_ACTION_MAP: dict[str, str] = {
        "POST":   "create",
        "PUT":    "update",
        "PATCH":  "patch",
        "DELETE": "delete",
        "GET":    "list",
        "HEAD":   "head",
    }

    try:
        admin_idx = path.index("/admin/")
        after_admin = path[admin_idx + len("/admin/"):].strip("/")
        segments = [s for s in after_admin.split("/") if s]

        if not segments:
            return "admin", METHOD_ACTION_MAP.get(method, "unknown")

        module = segments[0]

        if len(segments) == 1:
            # 单段：/admin/login, /admin/me, /admin/products
            # 固定动词语义的路径段直接作为 action
            if module in ("login", "logout", "refresh", "me"):
                return "admin", module
            action = METHOD_ACTION_MAP.get(method, "unknown")

        elif len(segments) == 2:
            # 两段：/admin/products/123 → 对特定资源操作
            last = segments[-1]
            action = METHOD_ACTION_MAP.get(method, "unknown") if _looks_like_id(last) else last

        else:
            # 三段及以上：/admin/orders/456/refund → action = refund
            last = segments[-1]
            action = last if not _looks_like_id(last) else METHOD_ACTION_MAP.get(method, "unknown")

    except (ValueError, IndexError):
        module = "unknown"
        action = METHOD_ACTION_MAP.get(method, "unknown")

    return module, action


def _looks_like_id(segment: str) -> bool:
    """判断路径片段是否为 ID (UUID 或纯数字)。"""
    if len(segment) in (32, 36) and "-" in segment:
        return True
    if segment.isdigit():
        return True
    return False
