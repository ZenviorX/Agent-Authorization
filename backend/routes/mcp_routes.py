from __future__ import annotations

import html
import os
from typing import Any, Dict
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from backend.mcp.service import (
    CURRENT_PROTOCOL_VERSION,
    InsufficientScopeError,
    McpProtocolError,
    handle_mcp_request,
    protocol_error_response,
)
from backend.mcp.tool_registry import supported_oauth_scopes
from backend.oauth.token_service import mcp_resource, oauth_issuer, verify_access_token


router = APIRouter(tags=["MCP + OAuth"])


def _resource_metadata_url(request: Request) -> str:
    configured = os.getenv("AGENTGUARD_OAUTH_RESOURCE_METADATA_URL")
    if configured:
        return configured
    return str(request.base_url).rstrip("/") + "/.well-known/oauth-protected-resource"


def _www_authenticate(request: Request, *, error: str = "", scopes: list[str] | None = None) -> str:
    parts = [
        "Bearer",
        f'resource_metadata="{_resource_metadata_url(request)}"',
    ]

    if error:
        parts.append(f'error="{error}"')

    normalized_scopes = [str(item) for item in scopes or [] if str(item)]
    if normalized_scopes:
        parts.append(f'scope="{" ".join(normalized_scopes)}"')

    return ", ".join(parts)


def _origin_allowed(origin: str | None) -> bool:
    if not origin:
        return True

    configured = {
        item.strip()
        for item in os.getenv("AGENTGUARD_MCP_ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    }
    if origin in configured:
        return True

    try:
        parsed = urlparse(origin)
    except Exception:
        return False

    return parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost"}


def _extract_bearer_token(request: Request) -> str:
    value = str(request.headers.get("authorization") or "").strip()
    if not value:
        return ""

    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return token.strip()


def _transport_header_error(payload: Dict[str, Any], request: Request) -> str | None:
    method = str(payload.get("method") or "")
    mirrored_method = str(request.headers.get("mcp-method") or "")
    if mirrored_method and mirrored_method != method:
        return "Mcp-Method header does not match the JSON-RPC method."

    if method == "tools/call":
        params = payload.get("params", {}) or {}
        name = str(params.get("name") or "") if isinstance(params, dict) else ""
        mirrored_name = str(request.headers.get("mcp-name") or "")
        if mirrored_name and mirrored_name != name:
            return "Mcp-Name header does not match params.name."

    return None


def _mcp_status_payload(request: Request) -> Dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    return {
        "status": "ok",
        "service": "AgentGuard MCP Security Gateway",
        "protocol_version": CURRENT_PROTOCOL_VERSION,
        "transport": "non-streaming Streamable HTTP",
        "protocol_endpoint": f"{base_url}/mcp",
        "protocol_method": "POST",
        "browser_info": f"{base_url}/mcp",
        "health_endpoint": f"{base_url}/mcp/status",
        "oauth_protected_resource_metadata": _resource_metadata_url(request),
        "oauth_issuer": oauth_issuer(),
        "supported_methods": [
            "initialize",
            "notifications/initialized",
            "ping",
            "tools/list",
            "tools/call",
        ],
        "note": (
            "Browsers send GET requests. MCP clients must send JSON-RPC with POST /mcp "
            "and a Bearer access token."
        ),
    }


def _mcp_status_html(request: Request) -> str:
    status = _mcp_status_payload(request)
    endpoint = html.escape(str(status["protocol_endpoint"]))
    metadata = html.escape(str(status["oauth_protected_resource_metadata"]))
    health = html.escape(str(status["health_endpoint"]))
    issuer = html.escape(str(status["oauth_issuer"]))
    protocol_version = html.escape(str(status["protocol_version"]))

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AgentGuard MCP Gateway</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }}
    main {{ max-width: 860px; margin: 48px auto; padding: 0 24px; }}
    .card {{ background: #111827; border: 1px solid #334155; border-radius: 16px; padding: 28px; box-shadow: 0 18px 45px rgba(0,0,0,.25); }}
    h1 {{ margin-top: 0; color: #f8fafc; }}
    .ok {{ display: inline-block; padding: 5px 10px; border-radius: 999px; background: #064e3b; color: #a7f3d0; font-weight: 700; }}
    code {{ background: #020617; padding: 3px 7px; border-radius: 6px; color: #93c5fd; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 22px; }}
    td {{ border-top: 1px solid #334155; padding: 12px 8px; vertical-align: top; }}
    td:first-child {{ width: 220px; color: #94a3b8; }}
    a {{ color: #7dd3fc; }}
    .notice {{ margin-top: 22px; padding: 14px 16px; border-left: 4px solid #38bdf8; background: #0c4a6e55; }}
  </style>
</head>
<body>
<main>
  <section class="card">
    <span class="ok">RUNNING</span>
    <h1>AgentGuard MCP Security Gateway</h1>
    <p>这是浏览器状态说明页，不是 MCP 工具调用结果页。</p>
    <table>
      <tr><td>MCP 协议版本</td><td><code>{protocol_version}</code></td></tr>
      <tr><td>MCP 调用端点</td><td><code>POST {endpoint}</code></td></tr>
      <tr><td>OAuth 资源元数据</td><td><a href="{metadata}">{metadata}</a></td></tr>
      <tr><td>OAuth Issuer</td><td><code>{issuer}</code></td></tr>
      <tr><td>JSON 健康状态</td><td><a href="{health}">{health}</a></td></tr>
    </table>
    <div class="notice">
      浏览器地址栏发送的是 GET 请求；真正的 MCP Client 必须携带 Bearer Token，使用 JSON-RPC <code>POST /mcp</code>。
    </div>
  </section>
</main>
</body>
</html>"""


@router.get("/.well-known/oauth-protected-resource")
def protected_resource_metadata() -> Dict[str, Any]:
    return {
        "resource": mcp_resource(),
        "authorization_servers": [oauth_issuer()],
        "scopes_supported": supported_oauth_scopes(),
        "bearer_methods_supported": ["header"],
        "resource_documentation": "MCP_OAUTH_QUICKSTART.md",
    }


@router.get("/.well-known/oauth-protected-resource/mcp")
def protected_resource_metadata_for_mcp_path() -> Dict[str, Any]:
    return protected_resource_metadata()


@router.get("/mcp/status")
def mcp_status(request: Request) -> Dict[str, Any]:
    """Browser/curl-safe health and integration information for the MCP gateway."""
    return _mcp_status_payload(request)


@router.get("/mcp")
def mcp_get(request: Request):
    """
    Render a human-readable page for normal browsers.

    A protocol client attempting GET/SSE still receives 405 because this
    competition implementation currently supports non-streaming POST only.
    """
    accept = str(request.headers.get("accept") or "").lower()
    if "text/html" in accept:
        return HTMLResponse(
            _mcp_status_html(request),
            status_code=200,
            headers={"Allow": "POST", "Cache-Control": "no-store"},
        )

    return JSONResponse(
        status_code=405,
        content={
            "error": "method_not_allowed",
            "message": (
                "This AgentGuard MCP endpoint accepts JSON-RPC through POST. "
                "Open /mcp in a normal browser for the information page or use /mcp/status for JSON health."
            ),
            "status_endpoint": "/mcp/status",
        },
        headers={"Allow": "POST", "Cache-Control": "no-store"},
    )


@router.post("/mcp")
async def mcp_post(request: Request):
    if not _origin_allowed(request.headers.get("origin")):
        return JSONResponse(
            status_code=403,
            content={"error": "invalid_origin", "message": "MCP Origin header is not allowed."},
        )

    access_token = _extract_bearer_token(request)
    if not access_token:
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_token", "message": "A Bearer access token is required."},
            headers={
                "WWW-Authenticate": _www_authenticate(request),
                "Cache-Control": "no-store",
            },
        )

    verified = verify_access_token(
        access_token,
        expected_audience=mcp_resource(),
        expected_issuer=oauth_issuer(),
    )
    if not verified.get("valid"):
        return JSONResponse(
            status_code=401,
            content={
                "error": str(verified.get("error") or "invalid_token"),
                "message": str(verified.get("reason") or "Access token is invalid."),
            },
            headers={
                "WWW-Authenticate": _www_authenticate(request, error="invalid_token"),
                "Cache-Control": "no-store",
            },
        )

    try:
        payload = await request.json()
    except Exception:
        error = McpProtocolError(-32700, "Request body is not valid JSON.")
        return JSONResponse(status_code=400, content=protocol_error_response(None, error))

    if not isinstance(payload, dict):
        error = McpProtocolError(-32600, "MCP request body must be a JSON object.")
        return JSONResponse(status_code=400, content=protocol_error_response(None, error))

    transport_error = _transport_header_error(payload, request)
    if transport_error:
        error = McpProtocolError(-32600, transport_error)
        return JSONResponse(status_code=400, content=protocol_error_response(payload.get("id"), error))

    if payload.get("method") == "tools/call":
        task_header = str(request.headers.get("x-agentguard-task") or "").strip()
        if task_header:
            params = payload.setdefault("params", {})
            if isinstance(params, dict):
                meta = params.setdefault("_meta", {})
                if isinstance(meta, dict):
                    meta.setdefault("agentguard/originalTask", task_header)

    principal = dict(verified.get("payload") or {})

    try:
        result = handle_mcp_request(payload, principal=principal)
    except InsufficientScopeError as exc:
        required = sorted(set(exc.required_scopes))
        return JSONResponse(
            status_code=403,
            content={
                "error": "insufficient_scope",
                "message": exc.message,
                "required_scopes": required,
            },
            headers={
                "WWW-Authenticate": _www_authenticate(
                    request,
                    error="insufficient_scope",
                    scopes=required,
                ),
                "Cache-Control": "no-store",
            },
        )
    except McpProtocolError as exc:
        return JSONResponse(
            status_code=200,
            content=protocol_error_response(payload.get("id"), exc),
            headers={"MCP-Protocol-Version": CURRENT_PROTOCOL_VERSION},
        )

    if result is None:
        return Response(status_code=202)

    return JSONResponse(
        status_code=200,
        content=result,
        headers={
            "MCP-Protocol-Version": CURRENT_PROTOCOL_VERSION,
            "Cache-Control": "no-store",
        },
    )