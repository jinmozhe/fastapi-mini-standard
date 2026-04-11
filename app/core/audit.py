"""
File: app/core/audit.py
Description: B端管理员操作审计日志中间件 (AuditLogMiddleware)

拦截所有 /admin/ 路径下的写操作 (POST/PUT/DELETE/PATCH)，
将操作者身份、请求快照存入 sys_audit_logs 表供事后追溯。

设计原则：
1. 精准拦截：只拦截 /admin/ 写操作，GET 请求和 C端接口不受影响。
2. 旁路提交：独立开启 DB Session 写日志，与主请求事务完全解耦。
3. Fail-Open：写日志失败绝对不影响业务响应，只记录错误日志。
4. 请求体重建：读取 body 后重新注入 receive，保障后续路由正常解析。

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

# 需要记录审计日志的写操作方法集合
AUDIT_METHODS: frozenset[str] = frozenset({"POST", "PUT", "DELETE", "PATCH"})

# 请求体快照的最大字节数（防止超大 Body 撑爆内存）
MAX_BODY_SIZE: int = 8 * 1024  # 8 KB

# 跳过审计的路径（登录/刷新/登出不需要记录操作内容，LoginLog 已经覆盖）
SKIP_AUDIT_PATHS: frozenset[str] = frozenset({
    "/admin/login",
    "/admin/refresh",
    "/admin/logout",
})


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    B端管理员操作审计日志中间件。

    工作流程：
    请求进入 → 判断是否需要审计
           ↓ 是
    提取 JWT admin_id（手动解析，不走 FastAPI 依赖注入）
           ↓
    读取请求体（截取 MAX_BODY_SIZE 字节）
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
        # 快速判断：只处理 /admin/ 路径下的写操作
        path = request.url.path
        method = request.method

        # /admin/login, /admin/refresh, /admin/logout 由 LoginLog 覆盖，跳过
        should_audit = (
            "/admin/" in path
            and method in AUDIT_METHODS
            and not any(path.endswith(skip) for skip in SKIP_AUDIT_PATHS)
        )

        if not should_audit:
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
                    options={"verify_aud": False, "verify_exp": False},  # 仅提取 sub，不强验证
                )
                if payload.get("aud") == "backend":
                    admin_id = payload.get("sub")
        except Exception:
            # JWT 解析失败不影响业务（业务层还会做正式校验）
            pass

        # ──────────────────────────────────────────────
        # 2. 读取请求体快照（截断超大 Payload，保护内存）
        # ──────────────────────────────────────────────
        body_bytes: bytes = b""
        payload_snapshot: dict | None = None

        try:
            body_bytes = await request.body()

            # 重建 receive 函数，保障后续路由层能正常解析 Body
            # 若不重建，路由拿到的 body 将是空的，导致 Pydantic 解析失败
            async def receive():
                return {"type": "http.request", "body": body_bytes, "more_body": False}

            request._receive = receive  # type: ignore[attr-defined]

            # 截取前 MAX_BODY_SIZE 字节，解析为 JSON（只关心写操作的结构化参数）
            if body_bytes:
                truncated = body_bytes[:MAX_BODY_SIZE]
                try:
                    payload_snapshot = json.loads(truncated)
                    # 脱敏处理：防止明文密码或敏感字段落入审计日志
                    _mask_sensitive_fields(payload_snapshot)
                except (json.JSONDecodeError, ValueError):
                    payload_snapshot = {"_raw": truncated.decode("utf-8", errors="replace")}
        except Exception as e:
            logger.warning(f"AuditLogMiddleware: Failed to read body: {e}")

        # ──────────────────────────────────────────────
        # 3. 执行主请求（任何情况下都不阻塞）
        # ──────────────────────────────────────────────
        response = await call_next(request)
        status_code: int = response.status_code

        # ──────────────────────────────────────────────
        # 4. 旁路写入审计日志（独立 Session，Fail-Open）
        # ──────────────────────────────────────────────
        # 解析模块与动作（从路径中提取，如 /admin/products → module=products）
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
            # Fail-Open：写日志失败不影响任何业务逻辑，只打印错误供排查
            logger.error(f"AuditLogMiddleware: Failed to write audit log: {e}")

        return response


# ==============================================================================
# 私有辅助函数
# ==============================================================================


def _mask_sensitive_fields(data: dict) -> None:
    """
    原地脱敏处理：将请求体 JSON 中的敏感字段值替换为 '***'。
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
    从请求路径和 HTTP 方法推断写入 AuditLog 的 module 和 action 字段。

    示例：
      POST  /api/v1/admin/products     → ("products", "create")
      DELETE /api/v1/admin/products/123 → ("products", "delete")
      PUT   /api/v1/admin/orders/456/refund → ("orders", "refund")
    """
    # HTTP 方法 → 默认动作映射
    METHOD_ACTION_MAP: dict[str, str] = {
        "POST":   "create",
        "PUT":    "update",
        "PATCH":  "patch",
        "DELETE": "delete",
    }

    # 从路径中提取 /admin/ 之后的第一个 segment 作为 module
    # 例如 /api/v1/admin/products/123 → segments=['products', '123']
    try:
        admin_idx = path.index("/admin/")
        after_admin = path[admin_idx + len("/admin/"):].strip("/")
        segments = [s for s in after_admin.split("/") if s]

        module = segments[0] if segments else "unknown"

        # 如果路径有 3+ 个 segment，最后一个可能是"动词型子操作"（如 refund, ban, approve）
        # 例如 /admin/orders/456/refund → action=refund
        if len(segments) >= 3 and not segments[-1].replace("-", "").isalnum():
            action = segments[-1]
        elif len(segments) >= 3:
            # /admin/orders/456/refund → segments[-1] = 'refund'（纯字母，非 ID）
            last = segments[-1]
            if not _looks_like_id(last):
                action = last
            else:
                action = METHOD_ACTION_MAP.get(method, "unknown")
        else:
            action = METHOD_ACTION_MAP.get(method, "unknown")
    except (ValueError, IndexError):
        module = "unknown"
        action = METHOD_ACTION_MAP.get(method, "unknown")

    return module, action


def _looks_like_id(segment: str) -> bool:
    """
    判断路径片段是否为 ID（UUID 格式或纯数字），用于区分 /refund vs /123。
    """
    # UUID 格式
    if len(segment) in (32, 36) and "-" in segment:
        return True
    # 纯数字
    if segment.isdigit():
        return True
    return False
