import pytest

from backend.mcp.service import (
    InsufficientScopeError,
    handle_mcp_request,
)


def _principal(scopes):
    return {
        "sub": "alice",
        "client_id": "test-mcp-client",
        "scope": " ".join(scopes),
        "scopes": list(scopes),
    }


def test_mcp_initialize_advertises_tools_capability():
    result = handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        },
        principal=_principal([]),
    )

    assert result["result"]["protocolVersion"] == "2025-11-25"
    assert "tools" in result["result"]["capabilities"]
    assert result["result"]["serverInfo"]["name"] == "agentguard-mcp-gateway"


def test_mcp_tools_list_uses_access_token_scopes():
    result = handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
        principal=_principal(["mcp:tools:list", "tool:file:read"]),
    )

    names = [tool["name"] for tool in result["result"]["tools"]]
    assert names == ["file.read"]


def test_mcp_tools_list_requires_list_scope():
    with pytest.raises(InsufficientScopeError) as captured:
        handle_mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/list",
                "params": {},
            },
            principal=_principal(["tool:file:read"]),
        )

    assert captured.value.required_scopes == ["mcp:tools:list"]


def test_mcp_tool_call_checks_dynamic_scopes_before_gateway_execution():
    with pytest.raises(InsufficientScopeError) as captured:
        handle_mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "email.send",
                    "arguments": {
                        "to": "outside@example.com",
                        "content": "public report",
                    },
                },
            },
            principal=_principal(["tool:email:send", "sink:side-effect"]),
        )

    assert captured.value.required_scopes == ["sink:external-email"]
