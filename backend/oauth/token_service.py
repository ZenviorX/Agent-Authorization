from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_OAUTH_ISSUER = "http://127.0.0.1:9000"
DEFAULT_MCP_RESOURCE = "http://127.0.0.1:8000/mcp"
DEFAULT_DEMO_SECRET = "agentguard-local-oauth-demo-secret-change-me"


def oauth_issuer() -> str:
    return os.getenv("AGENTGUARD_OAUTH_ISSUER", DEFAULT_OAUTH_ISSUER).rstrip("/")


def mcp_resource() -> str:
    return os.getenv("AGENTGUARD_MCP_RESOURCE", DEFAULT_MCP_RESOURCE).rstrip("/")


def _secret() -> bytes:
    return os.getenv("AGENTGUARD_OAUTH_DEMO_SECRET", DEFAULT_DEMO_SECRET).encode("utf-8")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _json_part(data: Dict[str, Any]) -> str:
    raw = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _b64url_encode(raw)


def normalize_scopes(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, str):
        raw_items = value.replace(",", " ").split()
    elif isinstance(value, Iterable):
        raw_items = [str(item) for item in value]
    else:
        raw_items = [str(value)]

    result: List[str] = []
    seen = set()

    for item in raw_items:
        scope = str(item).strip()
        if not scope or scope in seen:
            continue
        seen.add(scope)
        result.append(scope)

    return result


def _sign(signing_input: str) -> str:
    digest = hmac.new(
        _secret(),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


def issue_access_token(
    *,
    subject: str,
    scopes: Any,
    audience: Optional[str] = None,
    client_id: str = "agentguard-demo-client",
    ttl_seconds: int = 900,
    issuer: Optional[str] = None,
) -> Dict[str, Any]:
    now = int(time.time())
    normalized_scopes = normalize_scopes(scopes)

    header = {
        "alg": "HS256",
        "typ": "JWT",
    }
    payload = {
        "iss": issuer or oauth_issuer(),
        "sub": str(subject),
        "aud": audience or mcp_resource(),
        "client_id": str(client_id),
        "scope": " ".join(normalized_scopes),
        "iat": now,
        "exp": now + max(60, int(ttl_seconds)),
        "jti": secrets.token_urlsafe(12),
        "token_use": "access_token",
    }

    header_part = _json_part(header)
    payload_part = _json_part(payload)
    signing_input = f"{header_part}.{payload_part}"
    token = f"{signing_input}.{_sign(signing_input)}"

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": payload["exp"] - now,
        "scope": payload["scope"],
        "payload": payload,
    }


def _audience_matches(actual: Any, expected: str) -> bool:
    if isinstance(actual, list):
        return expected in [str(item) for item in actual]
    return str(actual or "") == expected


def verify_access_token(
    token: str,
    *,
    expected_audience: Optional[str] = None,
    expected_issuer: Optional[str] = None,
    now: Optional[int] = None,
) -> Dict[str, Any]:
    try:
        header_part, payload_part, signature = str(token).split(".", 2)
    except ValueError:
        return {"valid": False, "error": "malformed_token", "reason": "Access token is not a three-part JWT."}

    signing_input = f"{header_part}.{payload_part}"
    expected_signature = _sign(signing_input)

    if not hmac.compare_digest(signature, expected_signature):
        return {"valid": False, "error": "invalid_signature", "reason": "Access token signature verification failed."}

    try:
        header = json.loads(_b64url_decode(header_part).decode("utf-8"))
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except Exception as exc:
        return {"valid": False, "error": "invalid_encoding", "reason": f"Access token payload cannot be decoded: {exc}"}

    if header.get("alg") != "HS256":
        return {"valid": False, "error": "unsupported_alg", "reason": "Only HS256 is accepted by the local demo resource server."}

    current_time = int(time.time()) if now is None else int(now)
    expires_at = int(payload.get("exp", 0) or 0)

    if expires_at <= current_time:
        return {"valid": False, "error": "expired_token", "reason": "Access token has expired.", "payload": payload}

    issuer = expected_issuer or oauth_issuer()
    if str(payload.get("iss", "")).rstrip("/") != str(issuer).rstrip("/"):
        return {"valid": False, "error": "invalid_issuer", "reason": "Access token issuer does not match the configured authorization server.", "payload": payload}

    audience = expected_audience or mcp_resource()
    if not _audience_matches(payload.get("aud"), audience):
        return {"valid": False, "error": "invalid_audience", "reason": "Access token is not intended for this MCP resource.", "payload": payload}

    if payload.get("token_use") != "access_token":
        return {"valid": False, "error": "invalid_token_use", "reason": "Token is not an OAuth access token.", "payload": payload}

    payload = dict(payload)
    payload["scopes"] = normalize_scopes(payload.get("scope", ""))

    return {
        "valid": True,
        "payload": payload,
        "reason": "Access token signature, issuer, audience and expiry are valid.",
    }
