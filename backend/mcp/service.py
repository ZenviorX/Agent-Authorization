from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.mcp.tool_registry import (
    MCP_LIST_SCOPE,
    get_tool_definition,
    tool_definitions_for_scopes,
)
from backend.oauth.token_service import normalize_scopes
from backend.proxy.oauth_profile import get_required_scopes
from backend.proxy.proxy_models import ToolProxyAuthorizeRequest
from backend.proxy.tool_proxy_service import authorize_tool_call


CURRENT_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = (
    CURRENT_PROTOCOL_VERSION,
    "2025-06-18",
)


@dataclass
class McpProtocolError(Exception):
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


@dataclass
class InsufficientScopeError(Exception):
    required_scopes: List[str]
    message: str = "The OAuth access token does not contain all scopes required for this MCP operation."


def _response(request_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def protocol_error_response(request_id: Any, error: McpProtocolError) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": int(error.code),
            "message": str(error.message),
        },
    }

    if error.data:
        body["error"]["data"] = error.data

    return body


def _principal_scopes(principal: Dict[str, Any]) -> List[str]:
    return normalize_scopes(principal.get("scopes") or principal.get("scope") or [])


def _require_scopes(principal: Dict[str, Any], required: List[str]) -> None:
    granted = set(_principal_scopes(principal))
    missing = [scope for scope in normalize_scopes(required) if scope not in granted]

    if missing:
        raise InsufficientScopeError(required_scopes=missing)


def _select_protocol_version(requested: Any) -> str:
    requested_value = str(requested or "")
    if requested_value in SUPPORTED_PROTOCOL_VERSIONS:
        return requested_value
    return CURRENT_PROTOCOL_VERSION


def _initialize_result(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "protocolVersion": _select_protocol_version(params.get("protocolVersion")),
        "capabilities": {
            "tools": {
                "listChanged": False,
            }
        },
        "serverInfo": {
            "name": "agentguard-mcp-gateway",
            "version": "0.6.0",
        },
        "instructions": (
            "OAuth scopes provide coarse-grained access. AgentGuard additionally applies "
            "task-bound capability checks, runtime monitoring, sandbox policy and audit evidence "
            "before any MCP tool is executed. Pass the original user task in "
            "params._meta['agentguard/originalTask'] or the X-AgentGuard-Task HTTP header."
        ),
    }


def _tool_result_payload(
    *,
    decision: str,
    risk_score: int,
    reason: List[str],
    executed: bool,
    tool_result: Optional[Dict[str, Any]] = None,
    sandbox_evidence: Optional[Dict[str, Any]] = None,
    capability_token_validation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    structured = {
        "decision": str(decision),
        "risk_score": int(risk_score or 0),
        "reason": [str(item) for item in reason or []],
        "executed": bool(executed),
        "tool_result": tool_result,
        "sandbox_evidence": sandbox_evidence,
        "capability_token_validation": capability_token_validation or {},
    }

    tool_failed = bool(
        isinstance(tool_result, dict)
        and tool_result.get("success") is False
    )
    is_error = decision != "allow" or not executed or tool_failed

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(structured, ensure_ascii=False, indent=2),
            }
        ],
        "structuredContent": structured,
        "isError": is_error,
    }


def _extract_meta(params: Dict[str, Any]) -> Dict[str, Any]:
    meta = params.get("_meta", {}) or {}
    if not isinstance(meta, dict):
        raise McpProtocolError(-32602, "params._meta must be an object when provided.")
    return meta


def _prepare_proxy_request(
    *,
    principal: Dict[str, Any],
    name: str,
    arguments: Dict[str, Any],
    meta: Dict[str, Any],
) -> ToolProxyAuthorizeRequest:
    original_task = str(
        meta.get("agentguard/originalTask")
        or meta.get("agentguard.original_task")
        or f"Invoke MCP tool {name} with the supplied arguments."
    )

    input_labels = meta.get("agentguard/inputLabels", []) or []
    if not isinstance(input_labels, list):
        raise McpProtocolError(-32602, "agentguard/inputLabels must be an array.")

    input_from_steps = meta.get("agentguard/inputFromSteps", []) or []
    if not isinstance(input_from_steps, list):
        raise McpProtocolError(-32602, "agentguard/inputFromSteps must be an array.")

    try:
        confidence = float(meta.get("agentguard/agentConfidence", 1.0))
    except (TypeError, ValueError):
        raise McpProtocolError(-32602, "agentguard/agentConfidence must be numeric.")

    return ToolProxyAuthorizeRequest(
        user=str(principal.get("sub") or "oauth-user"),
        original_task=original_task,
        tool=name,
        params=arguments,
        input_labels=[str(item) for item in input_labels],
        input_from_steps=[int(item) for item in input_from_steps],
        agent_confidence=confidence,
        execute=False,
        agent_platform=str(meta.get("agentguard/agentPlatform") or principal.get("client_id") or "mcp-client"),
        auth_mode="oauth_scope",
        requested_scopes=_principal_scopes(principal),
        oauth_token_claims=dict(principal),
        capability_token="",
        sandbox_profile=str(meta.get("agentguard/sandboxProfile") or "default"),
        external_agent_metadata={
            "transport": "mcp_streamable_http",
            "mcp_protocol_version": str(meta.get("agentguard/protocolVersion") or CURRENT_PROTOCOL_VERSION),
        },
    )


def _call_tool(
    *,
    principal: Dict[str, Any],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    name = str(params.get("name") or "")
    arguments = params.get("arguments", {}) or {}

    if not name:
        raise McpProtocolError(-32602, "tools/call requires params.name.")

    if not isinstance(arguments, dict):
        raise McpProtocolError(-32602, "tools/call params.arguments must be an object.")

    if get_tool_definition(name) is None:
        raise McpProtocolError(-32602, f"Unknown MCP tool: {name}")

    dynamic_required_scopes = get_required_scopes(name, arguments)
    _require_scopes(principal, dynamic_required_scopes)

    meta = _extract_meta(params)
    prepare_request = _prepare_proxy_request(
        principal=principal,
        name=name,
        arguments=arguments,
        meta=meta,
    )
    prepare_result = authorize_tool_call(prepare_request)

    missing_scopes = list((prepare_result.agent_auth_profile or {}).get("missing_scopes", []))
    if missing_scopes:
        raise InsufficientScopeError(required_scopes=[str(item) for item in missing_scopes])

    if prepare_result.decision != "allow":
        return _tool_result_payload(
            decision=prepare_result.decision,
            risk_score=prepare_result.risk_score,
            reason=prepare_result.reason,
            executed=False,
            tool_result=None,
            sandbox_evidence=None,
            capability_token_validation=prepare_result.capability_token_validation,
        )

    token = str((prepare_result.capability_token or {}).get("token") or "")
    if not token:
        return _tool_result_payload(
            decision="deny",
            risk_score=max(100, int(prepare_result.risk_score or 0)),
            reason=list(prepare_result.reason) + ["AgentGuard did not issue the required task-scoped capability token."],
            executed=False,
        )

    execute_request = prepare_request.model_copy(
        update={
            "execute": True,
            "capability_token": token,
        }
    )
    execute_result = authorize_tool_call(execute_request)

    return _tool_result_payload(
        decision=execute_result.decision,
        risk_score=execute_result.risk_score,
        reason=execute_result.reason,
        executed=execute_result.executed,
        tool_result=execute_result.tool_result,
        sandbox_evidence=execute_result.sandbox_evidence,
        capability_token_validation=execute_result.capability_token_validation,
    )


def handle_mcp_request(
    payload: Dict[str, Any],
    *,
    principal: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        raise McpProtocolError(-32600, "MCP request must be a JSON object.")

    if payload.get("jsonrpc") != "2.0":
        raise McpProtocolError(-32600, "MCP uses JSON-RPC 2.0 and requires jsonrpc='2.0'.")

    request_id = payload.get("id")
    method = str(payload.get("method") or "")
    params = payload.get("params", {}) or {}

    if not method:
        raise McpProtocolError(-32600, "JSON-RPC method is required.")

    if not isinstance(params, dict):
        raise McpProtocolError(-32602, "JSON-RPC params must be an object.")

    if method == "notifications/initialized":
        return None

    if method == "initialize":
        return _response(request_id, _initialize_result(params))

    if method == "ping":
        return _response(request_id, {})

    if method == "tools/list":
        _require_scopes(principal, [MCP_LIST_SCOPE])
        return _response(
            request_id,
            {
                "tools": tool_definitions_for_scopes(_principal_scopes(principal)),
            },
        )

    if method == "tools/call":
        return _response(
            request_id,
            _call_tool(principal=principal, params=params),
        )

    raise McpProtocolError(-32601, f"MCP method not found: {method}")
