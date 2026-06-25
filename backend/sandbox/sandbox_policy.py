from __future__ import annotations

from typing import Any, Dict, List, Optional


SIDE_EFFECT_TOOLS = {
    "file.write",
    "file.delete",
    "email.send",
    "shell.run",
    "http.post",
    "db.write",
}

DANGEROUS_SHELL_KEYWORDS = [
    "rm -rf",
    "del /s",
    "format",
    "shutdown",
    "reboot",
    "curl",
    "wget",
    "powershell",
    "cmd.exe",
    "certutil",
    "bitsadmin",
    "nc ",
    "netcat",
    "ssh ",
    "scp ",
    "ftp ",
    "python -c",
    "bash -c",
    "sh -c",
]


SANDBOX_PROFILES: Dict[str, Dict[str, Any]] = {
    "default": {
        "description": "Default observation sandbox. It records sandbox context but does not add extra blocking.",
        "allowed_tools": ["*"],
        "denied_tools": [],
        "filesystem": "project_scoped",
        "network": "restricted",
        "shell_enabled": True,
        "side_effects": "runtime_controlled",
    },
    "local_readonly": {
        "description": "Read-only local sandbox. Only public/course read-like tools are expected.",
        "allowed_tools": ["file.read", "db.query"],
        "denied_tools": ["file.write", "file.delete", "email.send", "shell.run", "http.post"],
        "filesystem": "read_only_public_course",
        "network": "disabled",
        "shell_enabled": False,
        "side_effects": "blocked",
    },
    "local_safe_write": {
        "description": "Safe local write sandbox. Limited side effects may continue to Runtime Monitor and human approval.",
        "allowed_tools": ["file.read", "file.write", "db.query", "email.send"],
        "denied_tools": ["file.delete", "shell.run", "http.post"],
        "filesystem": "project_scoped_write",
        "network": "email_only_with_runtime_approval",
        "shell_enabled": False,
        "side_effects": "approval_required",
    },
    "no_shell": {
        "description": "Sandbox that allows normal tool calls but forbids shell execution.",
        "allowed_tools": ["*"],
        "denied_tools": ["shell.run"],
        "filesystem": "project_scoped",
        "network": "restricted",
        "shell_enabled": False,
        "side_effects": "runtime_controlled",
    },
    "strict": {
        "description": "Strict sandbox. Only read-only tools are allowed; side-effect tools are blocked.",
        "allowed_tools": ["file.read", "db.query"],
        "denied_tools": ["file.write", "file.delete", "email.send", "shell.run", "http.post"],
        "filesystem": "read_only_public_course",
        "network": "disabled",
        "shell_enabled": False,
        "side_effects": "blocked",
    },
}


def normalize_sandbox_profile(profile_name: Optional[str]) -> str:
    if not profile_name:
        return "default"

    normalized = str(profile_name).strip().lower()

    if normalized in SANDBOX_PROFILES:
        return normalized

    return "default"


def _contains_dangerous_shell_keyword(command: str) -> bool:
    lowered = command.lower()
    return any(keyword in lowered for keyword in DANGEROUS_SHELL_KEYWORDS)


def evaluate_sandbox_policy(
    profile_name: Optional[str],
    tool: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    params = params or {}
    normalized_profile = normalize_sandbox_profile(profile_name)
    profile = SANDBOX_PROFILES[normalized_profile]

    allowed_tools: List[str] = list(profile["allowed_tools"])
    denied_tools: List[str] = list(profile["denied_tools"])

    reasons: List[str] = [
        f"Sandbox profile={normalized_profile}.",
        str(profile["description"]),
    ]

    decision = "allow"
    risk_delta = 0

    if tool in denied_tools:
        decision = "deny"
        risk_delta = 100
        reasons.append(f"Tool {tool} is denied by sandbox profile {normalized_profile}.")

    elif "*" not in allowed_tools and tool not in allowed_tools:
        decision = "deny"
        risk_delta = 100
        reasons.append(f"Tool {tool} is not in allowed_tools of sandbox profile {normalized_profile}.")

    if tool == "shell.run":
        command = str(params.get("command") or params.get("cmd") or "")

        if not profile.get("shell_enabled", False):
            decision = "deny"
            risk_delta = 100
            reasons.append(f"Shell execution is disabled by sandbox profile {normalized_profile}.")

        if _contains_dangerous_shell_keyword(command):
            decision = "deny"
            risk_delta = 100
            reasons.append("Dangerous shell keyword detected by sandbox policy.")

    if normalized_profile in {"local_readonly", "strict"} and tool in SIDE_EFFECT_TOOLS:
        decision = "deny"
        risk_delta = 100
        reasons.append(f"Side-effect tool {tool} is blocked in {normalized_profile} sandbox.")

    return {
        "profile": normalized_profile,
        "decision": decision,
        "risk_delta": risk_delta,
        "reason": reasons,
        "policy": {
            "allowed_tools": allowed_tools,
            "denied_tools": denied_tools,
            "filesystem": profile["filesystem"],
            "network": profile["network"],
            "shell_enabled": profile["shell_enabled"],
            "side_effects": profile["side_effects"],
        },
    }
