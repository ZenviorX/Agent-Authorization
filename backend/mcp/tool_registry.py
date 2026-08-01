from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List

from backend.oauth.token_service import normalize_scopes


MCP_LIST_SCOPE = "mcp:tools:list"
MCP_TASK_SCOPE = "mcp:tasks:manage"
MCP_APPROVAL_READ_SCOPE = "mcp:approvals:read"
MCP_APPROVAL_DECIDE_SCOPE = "mcp:approvals:decide"


_TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "file.read",
        "title": "Read sandbox file",
        "description": "Read a file that is authorized by AgentGuard and confined to the runtime sandbox.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Sandbox-relative path, for example public/notice.txt.",
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "_meta": {
            "agentguard/requiredScopes": ["tool:file:read"],
        },
    },
    {
        "name": "file.write",
        "title": "Write sandbox file",
        "description": "Write content to an AgentGuard-authorized sandbox-relative file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "_meta": {
            "agentguard/requiredScopes": ["tool:file:write", "sink:side-effect"],
        },
    },
    {
        "name": "file.delete",
        "title": "Delete sandbox file",
        "description": "Delete an AgentGuard-authorized regular file inside the runtime sandbox.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        "_meta": {
            "agentguard/requiredScopes": ["tool:file:delete", "sink:side-effect"],
        },
    },
    {
        "name": "email.send",
        "title": "Send sandbox email",
        "description": "Create an email record in the sandbox outbox. The demo executor never sends real external email.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["to", "content"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        "_meta": {
            "agentguard/requiredScopes": ["tool:email:send", "sink:side-effect"],
        },
    },
    {
        "name": "shell.run",
        "title": "Run restricted sandbox command",
        "description": "Run a very small allowlist of commands through the AgentGuard sandbox interpreter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        "_meta": {
            "agentguard/requiredScopes": ["tool:shell:run", "sink:side-effect"],
        },
    },
    {
        "name": "db.query",
        "title": "Query sandbox database",
        "description": "Execute a read-only SELECT query against the AgentGuard sandbox database.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string"},
            },
            "required": ["sql"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "_meta": {
            "agentguard/requiredScopes": ["tool:db:query"],
        },
    },
]


def all_tool_definitions() -> List[Dict[str, Any]]:
    return [deepcopy(item) for item in sorted(_TOOL_DEFINITIONS, key=lambda tool: tool["name"])]


def required_list_scopes(tool: Dict[str, Any]) -> List[str]:
    meta = tool.get("_meta", {}) or {}
    return normalize_scopes(meta.get("agentguard/requiredScopes", []))


def tool_definitions_for_scopes(scopes: Iterable[str]) -> List[Dict[str, Any]]:
    granted = set(normalize_scopes(scopes))

    if MCP_LIST_SCOPE not in granted:
        return []

    visible: List[Dict[str, Any]] = []

    for tool in all_tool_definitions():
        required = set(required_list_scopes(tool))
        if required.issubset(granted):
            visible.append(tool)

    return visible


def get_tool_definition(name: str) -> Dict[str, Any] | None:
    normalized = str(name or "")
    for tool in _TOOL_DEFINITIONS:
        if tool["name"] == normalized:
            return deepcopy(tool)
    return None


def _supported_oauth_scopes_without_revocation() -> List[str]:
    values = {
        MCP_LIST_SCOPE,
        MCP_TASK_SCOPE,
        MCP_APPROVAL_READ_SCOPE,
        MCP_APPROVAL_DECIDE_SCOPE,
    }

    for tool in _TOOL_DEFINITIONS:
        values.update(
            required_list_scopes(tool)
        )

    values.update(
        {
            "sink:external-email",
            "source:sensitive-file",
        }
    )

    return sorted(values)


AGENTGUARD_REVOCATION_READ_SCOPE = (
    "mcp:revocations:read"
)

AGENTGUARD_REVOCATION_WRITE_SCOPE = (
    "mcp:revocations:write"
)


def supported_oauth_scopes():
    """
    Return all existing OAuth scopes plus the trusted
    revocation-management scopes.
    """
    existing = list(
        _supported_oauth_scopes_without_revocation()
    )

    for scope in (
        AGENTGUARD_REVOCATION_READ_SCOPE,
        AGENTGUARD_REVOCATION_WRITE_SCOPE,
    ):
        if scope not in existing:
            existing.append(scope)

    return existing
