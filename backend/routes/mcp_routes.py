from __future__ import annotations
import re
import asyncio
from collections import deque
import json
import threading
import time

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



MCP_MAX_BODY_BYTES_ENV = (
    "AGENTGUARD_MCP_MAX_BODY_BYTES"
)

MCP_RATE_LIMIT_ENABLED_ENV = (
    "AGENTGUARD_MCP_RATE_LIMIT_ENABLED"
)

MCP_RATE_LIMIT_REQUESTS_ENV = (
    "AGENTGUARD_MCP_RATE_LIMIT_REQUESTS"
)

MCP_RATE_LIMIT_WINDOW_ENV = (
    "AGENTGUARD_MCP_RATE_LIMIT_WINDOW_SECONDS"
)

MCP_MAX_CONCURRENT_ENV = (
    "AGENTGUARD_MCP_MAX_CONCURRENT_REQUESTS"
)


class McpIngressError(ValueError):
    def __init__(
        self,
        *,
        status_code: int,
        error: str,
        message: str,
    ):
        super().__init__(message)

        self.status_code = int(
            status_code
        )

        self.error = str(error)
        self.message = str(message)


class _SlidingWindowRateLimiter:
    def __init__(self):
        self._lock = (
            threading.Lock()
        )

        self._requests: dict[
            str,
            deque[float],
        ] = {}

    def check(
        self,
        *,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[
        bool,
        int,
        int,
    ]:
        now = time.monotonic()

        cutoff = (
            now
            - float(window_seconds)
        )

        with self._lock:
            queue = (
                self._requests
                .setdefault(
                    key,
                    deque(),
                )
            )

            while (
                queue
                and queue[0] <= cutoff
            ):
                queue.popleft()

            if len(queue) >= limit:
                retry_after = max(
                    1,
                    int(
                        queue[0]
                        + window_seconds
                        - now
                    )
                    + 1,
                )

                return (
                    False,
                    retry_after,
                    0,
                )

            queue.append(now)

            remaining = max(
                0,
                limit - len(queue),
            )

            self._prune_locked(
                now=now,
                window_seconds=(
                    window_seconds
                ),
            )

            return (
                True,
                0,
                remaining,
            )

    def _prune_locked(
        self,
        *,
        now: float,
        window_seconds: int,
    ) -> None:
        if len(self._requests) <= 10000:
            return

        stale_before = (
            now
            - float(
                window_seconds * 2
            )
        )

        stale_keys = [
            key
            for key, queue
            in self._requests.items()
            if (
                not queue
                or queue[-1]
                < stale_before
            )
        ]

        for key in stale_keys:
            self._requests.pop(
                key,
                None,
            )

        while (
            len(self._requests)
            > 10000
        ):
            oldest_key = next(
                iter(self._requests)
            )

            self._requests.pop(
                oldest_key,
                None,
            )

    def clear(self) -> None:
        with self._lock:
            self._requests.clear()


class _ConcurrencyGate:
    def __init__(self):
        self._lock = (
            threading.Lock()
        )

        self._active = 0

    def try_acquire(
        self,
        limit: int,
    ) -> bool:
        with self._lock:
            if self._active >= limit:
                return False

            self._active += 1
            return True

    def release(self) -> None:
        with self._lock:
            if self._active > 0:
                self._active -= 1

    def reset(self) -> None:
        with self._lock:
            self._active = 0


_MCP_RATE_LIMITER = (
    _SlidingWindowRateLimiter()
)

_MCP_CONCURRENCY_GATE = (
    _ConcurrencyGate()
)


def _bounded_integer_environment(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw_value = str(
        os.getenv(
            name,
            str(default),
        )
        or default
    ).strip()

    try:
        value = int(raw_value)

    except ValueError:
        value = default

    return max(
        minimum,
        min(value, maximum),
    )


def _boolean_environment(
    name: str,
    *,
    default: bool,
) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return str(
        value
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _mcp_ingress_config(
) -> dict[str, Any]:
    competition_mode = (
        os.getenv(
            "AGENTGUARD_MODE",
            "demo",
        ).strip().lower()
        == "competition"
    )

    return {
        "max_body_bytes": (
            _bounded_integer_environment(
                MCP_MAX_BODY_BYTES_ENV,
                256 * 1024,
                minimum=64,
                maximum=(
                    10 * 1024 * 1024
                ),
            )
        ),
        "rate_limit_enabled": (
            _boolean_environment(
                MCP_RATE_LIMIT_ENABLED_ENV,
                default=competition_mode,
            )
        ),
        "rate_limit_requests": (
            _bounded_integer_environment(
                MCP_RATE_LIMIT_REQUESTS_ENV,
                120,
                minimum=1,
                maximum=100000,
            )
        ),
        "rate_limit_window_seconds": (
            _bounded_integer_environment(
                MCP_RATE_LIMIT_WINDOW_ENV,
                60,
                minimum=1,
                maximum=3600,
            )
        ),
        "max_concurrent_requests": (
            _bounded_integer_environment(
                MCP_MAX_CONCURRENT_ENV,
                8,
                minimum=1,
                maximum=256,
            )
        ),
    }


def _declared_content_length_error(
    request: Request,
    *,
    max_body_bytes: int,
) -> McpIngressError | None:
    raw_value = str(
        request.headers.get(
            "content-length"
        )
        or ""
    ).strip()

    if not raw_value:
        return None

    try:
        content_length = int(
            raw_value
        )

    except ValueError:
        return McpIngressError(
            status_code=400,
            error=(
                "invalid_content_length"
            ),
            message=(
                "Content-Length must be "
                "a non-negative integer."
            ),
        )

    if content_length < 0:
        return McpIngressError(
            status_code=400,
            error=(
                "invalid_content_length"
            ),
            message=(
                "Content-Length must be "
                "non-negative."
            ),
        )

    if content_length > max_body_bytes:
        return McpIngressError(
            status_code=413,
            error="request_too_large",
            message=(
                "MCP request body exceeds "
                f"the {max_body_bytes}-byte "
                "limit."
            ),
        )

    return None


async def _read_limited_request_body(
    request: Request,
    *,
    max_body_bytes: int,
) -> bytes:
    declared_error = (
        _declared_content_length_error(
            request,
            max_body_bytes=(
                max_body_bytes
            ),
        )
    )

    if declared_error is not None:
        raise declared_error

    body_parts: list[bytes] = []
    body_size = 0

    async for chunk in request.stream():
        body_size += len(chunk)

        if body_size > max_body_bytes:
            raise McpIngressError(
                status_code=413,
                error="request_too_large",
                message=(
                    "MCP request body exceeds "
                    f"the {max_body_bytes}-byte "
                    "limit."
                ),
            )

        body_parts.append(chunk)

    return b"".join(body_parts)


def _mcp_rate_limit_key(
    request: Request,
    principal: dict[str, Any],
) -> str:
    subject = str(
        principal.get("sub")
        or "unknown-subject"
    ).strip()

    client_id = str(
        principal.get("client_id")
        or principal.get("azp")
        or "unknown-client"
    ).strip()

    client = request.client

    source_host = str(
        client.host
        if client is not None
        else "unknown-source"
    ).strip()

    return (
        subject
        + "|"
        + client_id
        + "|"
        + source_host
    )


def _reset_mcp_ingress_state(
) -> None:
    _MCP_RATE_LIMITER.clear()
    _MCP_CONCURRENCY_GATE.reset()



from backend.task_session.task_store import (
    abandon_mcp_idempotency_key,
    claim_mcp_idempotency_key,
    complete_mcp_idempotency_key,
)


MCP_IDEMPOTENCY_REQUIRED_ENV = (
    "AGENTGUARD_MCP_IDEMPOTENCY_REQUIRED"
)

MCP_IDEMPOTENCY_TTL_ENV = (
    "AGENTGUARD_MCP_IDEMPOTENCY_TTL_SECONDS"
)

MCP_IDEMPOTENCY_HEADER = (
    "Idempotency-Key"
)

_MCP_IDEMPOTENCY_KEY_PATTERN = re.compile(
    r"^[A-Za-z0-9._:-]{16,200}$"
)


def _mcp_idempotency_required(
) -> bool:
    competition_mode = (
        os.getenv(
            "AGENTGUARD_MODE",
            "demo",
        ).strip().lower()
        == "competition"
    )

    return _boolean_environment(
        MCP_IDEMPOTENCY_REQUIRED_ENV,
        default=competition_mode,
    )


def _mcp_idempotency_ttl_seconds(
) -> int:
    return _bounded_integer_environment(
        MCP_IDEMPOTENCY_TTL_ENV,
        24 * 60 * 60,
        minimum=60,
        maximum=7 * 24 * 60 * 60,
    )


def _extract_mcp_idempotency_key(
    request: Request,
) -> str:
    value = str(
        request.headers.get(
            MCP_IDEMPOTENCY_HEADER
        )
        or request.headers.get(
            "x-agentguard-idempotency-key"
        )
        or ""
    ).strip()

    if not value:
        return ""

    if not (
        _MCP_IDEMPOTENCY_KEY_PATTERN
        .fullmatch(value)
    ):
        raise McpIngressError(
            status_code=400,
            error=(
                "invalid_idempotency_key"
            ),
            message=(
                "Idempotency-Key must contain "
                "16 to 200 letters, digits, "
                "periods, underscores, colons "
                "or hyphens."
            ),
        )

    return value


def _idempotency_request_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    semantic_payload = dict(payload)

    # JSON-RPC id identifies the transport
    # exchange, not the requested side effect.
    semantic_payload.pop(
        "id",
        None,
    )

    return semantic_payload


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
async def mcp_post(
    request: Request,
):
    if not _origin_allowed(
        request.headers.get("origin")
    ):
        return JSONResponse(
            status_code=403,
            content={
                "error": "invalid_origin",
                "message": (
                    "MCP Origin header "
                    "is not allowed."
                ),
            },
            headers={
                "Cache-Control": "no-store",
            },
        )

    ingress_config = (
        _mcp_ingress_config()
    )

    declared_error = (
        _declared_content_length_error(
            request,
            max_body_bytes=int(
                ingress_config[
                    "max_body_bytes"
                ]
            ),
        )
    )

    if declared_error is not None:
        return JSONResponse(
            status_code=(
                declared_error.status_code
            ),
            content={
                "error": (
                    declared_error.error
                ),
                "message": (
                    declared_error.message
                ),
                "max_body_bytes": int(
                    ingress_config[
                        "max_body_bytes"
                    ]
                ),
            },
            headers={
                "Cache-Control": "no-store",
            },
        )

    access_token = (
        _extract_bearer_token(
            request
        )
    )

    if not access_token:
        return JSONResponse(
            status_code=401,
            content={
                "error": "invalid_token",
                "message": (
                    "A Bearer access token "
                    "is required."
                ),
            },
            headers={
                "WWW-Authenticate": (
                    _www_authenticate(request)
                ),
                "Cache-Control": "no-store",
            },
        )

    verified = verify_access_token(
        access_token,
        expected_audience=(
            mcp_resource()
        ),
        expected_issuer=(
            oauth_issuer()
        ),
    )

    if not verified.get("valid"):
        return JSONResponse(
            status_code=401,
            content={
                "error": str(
                    verified.get("error")
                    or "invalid_token"
                ),
                "message": str(
                    verified.get("reason")
                    or (
                        "Access token "
                        "is invalid."
                    )
                ),
            },
            headers={
                "WWW-Authenticate": (
                    _www_authenticate(
                        request,
                        error="invalid_token",
                    )
                ),
                "Cache-Control": "no-store",
            },
        )

    principal = dict(
        verified.get("payload")
        or {}
    )

    if ingress_config[
        "rate_limit_enabled"
    ]:
        (
            allowed,
            retry_after,
            remaining,
        ) = _MCP_RATE_LIMITER.check(
            key=_mcp_rate_limit_key(
                request,
                principal,
            ),
            limit=int(
                ingress_config[
                    "rate_limit_requests"
                ]
            ),
            window_seconds=int(
                ingress_config[
                    "rate_limit_window_seconds"
                ]
            ),
        )

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": (
                        "rate_limit_exceeded"
                    ),
                    "message": (
                        "OAuth principal exceeded "
                        "the MCP request rate limit."
                    ),
                    "retry_after_seconds": (
                        retry_after
                    ),
                },
                headers={
                    "Retry-After": str(
                        retry_after
                    ),
                    "X-RateLimit-Limit": str(
                        ingress_config[
                            "rate_limit_requests"
                        ]
                    ),
                    "X-RateLimit-Remaining": (
                        "0"
                    ),
                    "Cache-Control": "no-store",
                },
            )

    try:
        raw_body = (
            await _read_limited_request_body(
                request,
                max_body_bytes=int(
                    ingress_config[
                        "max_body_bytes"
                    ]
                ),
            )
        )

    except McpIngressError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error,
                "message": exc.message,
                "max_body_bytes": int(
                    ingress_config[
                        "max_body_bytes"
                    ]
                ),
            },
            headers={
                "Cache-Control": "no-store",
            },
        )

    try:
        payload = json.loads(
            raw_body.decode("utf-8")
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        error = McpProtocolError(
            -32700,
            (
                "Request body is not "
                "valid JSON."
            ),
        )

        return JSONResponse(
            status_code=400,
            content=(
                protocol_error_response(
                    None,
                    error,
                )
            ),
            headers={
                "Cache-Control": "no-store",
            },
        )

    if not isinstance(payload, dict):
        error = McpProtocolError(
            -32600,
            (
                "MCP request body must "
                "be a JSON object."
            ),
        )

        return JSONResponse(
            status_code=400,
            content=(
                protocol_error_response(
                    None,
                    error,
                )
            ),
            headers={
                "Cache-Control": "no-store",
            },
        )

    transport_error = (
        _transport_header_error(
            payload,
            request,
        )
    )

    if transport_error:
        error = McpProtocolError(
            -32600,
            transport_error,
        )

        return JSONResponse(
            status_code=400,
            content=(
                protocol_error_response(
                    payload.get("id"),
                    error,
                )
            ),
            headers={
                "Cache-Control": "no-store",
            },
        )

    if (
        payload.get("method")
        == "tools/call"
    ):
        task_handle_header = str(
            request.headers.get(
                "x-agentguard-task-handle"
            )
            or ""
        ).strip()

        if task_handle_header:
            params = payload.setdefault(
                "params",
                {},
            )

            if isinstance(params, dict):
                meta = params.setdefault(
                    "_meta",
                    {},
                )

                if isinstance(meta, dict):
                    meta.setdefault(
                        "agentguard/taskHandle",
                        task_handle_header,
                    )

    idempotency_context = None
    idempotency_key = ""

    if (
        payload.get("method")
        == "tools/call"
    ):
        try:
            idempotency_key = (
                _extract_mcp_idempotency_key(
                    request
                )
            )

        except McpIngressError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": exc.error,
                    "message": exc.message,
                },
                headers={
                    "Cache-Control": (
                        "no-store"
                    ),
                },
            )

        if (
            not idempotency_key
            and _mcp_idempotency_required()
        ):
            return JSONResponse(
                status_code=428,
                content={
                    "error": (
                        "idempotency_key_required"
                    ),
                    "message": (
                        "MCP tools/call requires "
                        "an Idempotency-Key header "
                        "in competition mode."
                    ),
                    "required_header": (
                        MCP_IDEMPOTENCY_HEADER
                    ),
                },
                headers={
                    "Cache-Control": "no-store",
                },
            )

        if idempotency_key:
            subject = str(
                principal.get("sub")
                or ""
            ).strip()

            client_id = str(
                principal.get("client_id")
                or principal.get("azp")
                or ""
            ).strip()

            claim = await asyncio.to_thread(
                claim_mcp_idempotency_key,
                subject=subject,
                client_id=client_id,
                idempotency_key=(
                    idempotency_key
                ),
                request_payload=(
                    _idempotency_request_payload(
                        payload
                    )
                ),
                ttl_seconds=(
                    _mcp_idempotency_ttl_seconds()
                ),
            )

            claim_state = str(
                claim.get("state")
                or ""
            )

            if claim_state == "conflict":
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": (
                            "idempotency_conflict"
                        ),
                        "message": str(
                            claim.get("reason")
                            or (
                                "Idempotency-Key "
                                "is already bound "
                                "to another request."
                            )
                        ),
                    },
                    headers={
                        "Cache-Control": (
                            "no-store"
                        ),
                    },
                )

            if claim_state == "in_progress":
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": (
                            "idempotency_in_progress"
                        ),
                        "message": str(
                            claim.get("reason")
                            or (
                                "An identical request "
                                "is already running."
                            )
                        ),
                    },
                    headers={
                        "Retry-After": "1",
                        "Cache-Control": (
                            "no-store"
                        ),
                    },
                )

            if claim_state == "corrupted":
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": (
                            "idempotency_store_corrupt"
                        ),
                        "message": str(
                            claim.get("reason")
                            or (
                                "Stored idempotency "
                                "response is invalid."
                            )
                        ),
                    },
                    headers={
                        "Cache-Control": (
                            "no-store"
                        ),
                    },
                )

            if claim_state == "completed":
                cached_body = (
                    claim.get(
                        "response_body"
                    )
                )

                if isinstance(
                    cached_body,
                    dict,
                ):
                    cached_body = dict(
                        cached_body
                    )

                    if (
                        cached_body.get(
                            "jsonrpc"
                        )
                        == "2.0"
                    ):
                        cached_body["id"] = (
                            payload.get("id")
                        )

                return JSONResponse(
                    status_code=int(
                        claim.get(
                            "http_status"
                        )
                        or 200
                    ),
                    content=cached_body,
                    headers={
                        "Idempotency-Key": (
                            idempotency_key
                        ),
                        (
                            "X-AgentGuard-"
                            "Idempotent-Replay"
                        ): "true",
                        "Cache-Control": (
                            "no-store"
                        ),
                    },
                )

            if claim_state != "acquired":
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": (
                            "idempotency_claim_failed"
                        ),
                        "message": (
                            "AgentGuard could not "
                            "acquire a trusted "
                            "idempotency claim."
                        ),
                    },
                    headers={
                        "Cache-Control": (
                            "no-store"
                        ),
                    },
                )

            idempotency_context = claim

    async def final_response(
        *,
        status_code: int,
        content,
        headers=None,
    ):
        response_headers = dict(
            headers or {}
        )

        response_headers.setdefault(
            "Cache-Control",
            "no-store",
        )

        if idempotency_context is not None:
            completion = (
                await asyncio.to_thread(
                    complete_mcp_idempotency_key,
                    key_hash=str(
                        idempotency_context[
                            "key_hash"
                        ]
                    ),
                    request_hash=str(
                        idempotency_context[
                            "request_hash"
                        ]
                    ),
                    claim_token=str(
                        idempotency_context[
                            "claim_token"
                        ]
                    ),
                    http_status=int(
                        status_code
                    ),
                    response_body=content,
                )
            )

            if not completion.get(
                "completed"
            ):
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": (
                            "idempotency_"
                            "finalization_failed"
                        ),
                        "message": (
                            "The MCP result was "
                            "produced, but its "
                            "idempotency record "
                            "could not be finalized."
                        ),
                    },
                    headers={
                        "Cache-Control": (
                            "no-store"
                        ),
                    },
                )

            response_headers[
                "Idempotency-Key"
            ] = idempotency_key

            response_headers[
                (
                    "X-AgentGuard-"
                    "Idempotent-Replay"
                )
            ] = "false"

        if content is None:
            return Response(
                status_code=status_code,
                headers=response_headers,
            )

        return JSONResponse(
            status_code=status_code,
            content=content,
            headers=response_headers,
        )

    acquired = (
        _MCP_CONCURRENCY_GATE
        .try_acquire(
            int(
                ingress_config[
                    "max_concurrent_requests"
                ]
            )
        )
    )

    if not acquired:
        if idempotency_context is not None:
            await asyncio.to_thread(
                abandon_mcp_idempotency_key,
                key_hash=str(
                    idempotency_context[
                        "key_hash"
                    ]
                ),
                request_hash=str(
                    idempotency_context[
                        "request_hash"
                    ]
                ),
                claim_token=str(
                    idempotency_context[
                        "claim_token"
                    ]
                ),
            )

        return JSONResponse(
            status_code=503,
            content={
                "error": (
                    "mcp_capacity_exceeded"
                ),
                "message": (
                    "MCP execution capacity "
                    "is temporarily exhausted."
                ),
            },
            headers={
                "Retry-After": "1",
                "Cache-Control": "no-store",
            },
        )

    try:
        try:
            result = await asyncio.to_thread(
                handle_mcp_request,
                payload,
                principal=principal,
            )

        except InsufficientScopeError as exc:
            required = sorted(
                set(exc.required_scopes)
            )

            return await final_response(
                status_code=403,
                content={
                    "error": (
                        "insufficient_scope"
                    ),
                    "message": exc.message,
                    "required_scopes": (
                        required
                    ),
                },
                headers={
                    "WWW-Authenticate": (
                        _www_authenticate(
                            request,
                            error=(
                                "insufficient_scope"
                            ),
                            scopes=required,
                        )
                    ),
                },
            )

        except McpProtocolError as exc:
            return await final_response(
                status_code=200,
                content=(
                    protocol_error_response(
                        payload.get("id"),
                        exc,
                    )
                ),
                headers={
                    "MCP-Protocol-Version": (
                        CURRENT_PROTOCOL_VERSION
                    ),
                },
            )

        except Exception:
            # The handler may already have entered a
            # side-effecting execution path. Keep the
            # idempotency claim in processing state so
            # a blind retry cannot execute it again.
            return JSONResponse(
                status_code=500,
                content={
                    "error": (
                        "mcp_execution_"
                        "state_unknown"
                    ),
                    "message": (
                        "The MCP execution ended "
                        "unexpectedly. AgentGuard "
                        "kept the idempotency claim "
                        "locked to prevent a "
                        "duplicate side effect."
                    ),
                },
                headers={
                    (
                        "X-AgentGuard-"
                        "Idempotency-State"
                    ): (
                        "indeterminate"
                        if idempotency_context
                        is not None
                        else "not_applicable"
                    ),
                    "Cache-Control": "no-store",
                },
            )

    finally:
        _MCP_CONCURRENCY_GATE.release()

    if result is None:
        return await final_response(
            status_code=202,
            content=None,
        )

    return await final_response(
        status_code=200,
        content=result,
        headers={
            "MCP-Protocol-Version": (
                CURRENT_PROTOCOL_VERSION
            ),
        },
    )
