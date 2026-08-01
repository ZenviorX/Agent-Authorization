from __future__ import annotations

import os
from typing import Any, Dict
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

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


@router.get("/mcp")
def mcp_get_not_streaming() -> JSONResponse:
    return JSONResponse(
        status_code=405,
        content={
            "error": "method_not_allowed",
            "message": "This minimal AgentGuard MCP endpoint uses non-streaming Streamable HTTP POST requests.",
        },
        headers={"Allow": "POST"},
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
