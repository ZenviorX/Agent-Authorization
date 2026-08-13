from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict


DEFAULT_AUTH_SERVER = "http://127.0.0.1:9000"
DEFAULT_MCP_ENDPOINT = "http://127.0.0.1:8000/mcp"
DEFAULT_CLIENT_ID = "agentguard-demo-client"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"
DEFAULT_SCOPES = "mcp:tools:list mcp:tasks:manage tool:file:read"
PROTOCOL_VERSION = "2025-11-25"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def _authorization_code(
    *,
    auth_server: str,
    client_id: str,
    redirect_uri: str,
    scopes: str,
    resource: str,
) -> tuple[str, str]:
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(16)
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": resource,
            "approve": "true",
        }
    )
    request = urllib.request.Request(f"{auth_server.rstrip('/')}/authorize?{query}")
    opener = urllib.request.build_opener(_NoRedirect)

    location = ""
    try:
        response = opener.open(request, timeout=10)
        location = response.headers.get("Location", "")
    except urllib.error.HTTPError as exc:
        if exc.code != 302:
            raise
        location = exc.headers.get("Location", "")

    if not location:
        raise RuntimeError("OAuth authorization endpoint did not return a redirect URI.")

    parsed = urllib.parse.urlparse(location)
    values = urllib.parse.parse_qs(parsed.query)

    returned_state = values.get("state", [""])[0]
    if returned_state != state:
        raise RuntimeError("OAuth state mismatch.")

    if values.get("error"):
        raise RuntimeError(
            f"OAuth authorization failed: {values.get('error', [''])[0]} "
            f"{values.get('error_description', [''])[0]}"
        )

    code = values.get("code", [""])[0]
    if not code:
        raise RuntimeError("OAuth authorization redirect did not contain a code.")

    return code, verifier


def _exchange_token(
    *,
    auth_server: str,
    client_id: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
    resource: str,
) -> Dict[str, Any]:
    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code": code,
            "code_verifier": code_verifier,
            "resource": resource,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{auth_server.rstrip('/')}/token",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _mcp_request(
    *,
    endpoint: str,
    access_token: str,
    payload: Dict[str, Any],
) -> Dict[str, Any] | None:
    method = str(payload.get("method") or "")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": method,
    }

    if method == "tools/call":
        params = payload.get("params", {}) or {}
        headers["Mcp-Name"] = str(params.get("name") or "")

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers=headers,
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        challenge = exc.headers.get("WWW-Authenticate", "")
        raise RuntimeError(
            f"MCP HTTP {exc.code}: {raw}\nWWW-Authenticate: {challenge}"
        ) from exc


def run_demo(args: argparse.Namespace) -> int:
    code, verifier = _authorization_code(
        auth_server=args.auth_server,
        client_id=args.client_id,
        redirect_uri=args.redirect_uri,
        scopes=args.scopes,
        resource=args.mcp_endpoint,
    )
    token_response = _exchange_token(
        auth_server=args.auth_server,
        client_id=args.client_id,
        redirect_uri=args.redirect_uri,
        code=code,
        code_verifier=verifier,
        resource=args.mcp_endpoint,
    )
    access_token = str(token_response.get("access_token") or "")
    if not access_token:
        raise RuntimeError(f"OAuth token response does not contain access_token: {token_response}")

    print("\n=== OAuth token acquired ===")
    print(json.dumps({key: value for key, value in token_response.items() if key != "access_token"}, ensure_ascii=False, indent=2))

    initialize = _mcp_request(
        endpoint=args.mcp_endpoint,
        access_token=access_token,
        payload={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "agentguard-python-demo-client",
                    "version": "0.1.0",
                },
            },
        },
    )
    print("\n=== MCP initialize ===")
    print(json.dumps(initialize, ensure_ascii=False, indent=2))

    _mcp_request(
        endpoint=args.mcp_endpoint,
        access_token=access_token,
        payload={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
    )

    tools = _mcp_request(
        endpoint=args.mcp_endpoint,
        access_token=access_token,
        payload={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
    )
    print("\n=== OAuth-filtered tools/list ===")
    print(json.dumps(tools, ensure_ascii=False, indent=2))

    if args.discover_only:
        return 0

    task_response = _mcp_request(
        endpoint=args.mcp_endpoint,
        access_token=access_token,
        payload={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "agentguard/tasks/create",
            "params": {
                "originalTask": args.task,
            },
        },
    )

    print("\n=== Trusted task created ===")
    print(json.dumps(task_response, ensure_ascii=False, indent=2))

    task_handle = str(
        ((task_response or {}).get("result") or {}).get("taskHandle")
        or ""
    )

    if not task_handle:
        raise RuntimeError(
            "agentguard/tasks/create did not return taskHandle."
        )

    try:
        arguments = json.loads(args.arguments_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"--arguments-json is invalid JSON: {exc}") from exc

    if not isinstance(arguments, dict):
        raise RuntimeError("--arguments-json must decode to a JSON object.")

    call_result = _mcp_request(
        endpoint=args.mcp_endpoint,
        access_token=access_token,
        payload={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": args.tool,
                "arguments": arguments,
                "_meta": {
                    "agentguard/taskHandle": task_handle,
                    "agentguard/sandboxProfile": args.sandbox_profile,
                    "agentguard/agentPlatform": "python-demo-client",
                },
            },
        },
    )
    print("\n=== MCP tools/call through AgentGuard ===")
    print(json.dumps(call_result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the localhost OAuth + MCP + AgentGuard competition demo."
    )
    parser.add_argument("--auth-server", default=DEFAULT_AUTH_SERVER)
    parser.add_argument("--mcp-endpoint", default=DEFAULT_MCP_ENDPOINT)
    parser.add_argument("--client-id", default=DEFAULT_CLIENT_ID)
    parser.add_argument("--redirect-uri", default=DEFAULT_REDIRECT_URI)
    parser.add_argument("--scopes", default=DEFAULT_SCOPES)
    parser.add_argument(
        "--task",
        default="读取 public/notice.txt 并总结，不要修改或向外发送任何内容。",
    )
    parser.add_argument("--tool", default="file.read")
    parser.add_argument("--arguments-json", default='{"path": "public/notice.txt"}')
    parser.add_argument("--sandbox-profile", default="default")
    parser.add_argument("--discover-only", action="store_true")
    return parser


def main() -> int:
    try:
        return run_demo(build_parser().parse_args())
    except Exception as exc:
        print(f"[demo-error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
