from __future__ import annotations

import json
import os
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple


WORKSPACE = Path("/workspace")
MAX_READ_BYTES = 512 * 1024
SAFE_SHELL_COMMANDS = {"echo", "pwd", "ls", "cat"}


class SandboxDenied(Exception):
    pass


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_rel_path(raw: Any) -> str:
    path = str(raw or "").strip().replace("\\", "/")

    while path.startswith("./"):
        path = path[2:]

    if not path:
        raise SandboxDenied("File path is empty.")

    first = path.split("/", 1)[0]
    if path.startswith("/") or ":" in first:
        raise SandboxDenied("Absolute path or drive-letter path is denied inside Docker sandbox.")

    if "../" in path or path == ".." or path.startswith("../"):
        raise SandboxDenied("Path traversal is denied inside Docker sandbox.")

    return path


def _resolve_workspace_path(raw: Any) -> Tuple[Path, str]:
    rel = _normalize_rel_path(raw)
    target = (WORKSPACE / rel).resolve()

    try:
        target.relative_to(WORKSPACE.resolve())
    except ValueError as exc:
        raise SandboxDenied("Path escapes /workspace.") from exc

    return target, rel


def _get_path(params: Dict[str, Any]) -> Any:
    return params.get("path") or params.get("file_path") or params.get("resource") or params.get("filename")


def _read_file(params: Dict[str, Any]) -> Dict[str, Any]:
    path, rel = _resolve_workspace_path(_get_path(params))

    if not path.exists():
        raise SandboxDenied(f"File does not exist in mounted workspace: {rel}")

    if not path.is_file():
        raise SandboxDenied(f"Target is not a regular file: {rel}")

    size = path.stat().st_size
    if size > MAX_READ_BYTES:
        raise SandboxDenied("File is too large for sandbox read.")

    content = path.read_text(encoding="utf-8", errors="replace")
    return {
        "success": True,
        "result": content,
        "meta": {
            "path": rel,
            "bytes": len(content.encode("utf-8")),
            "workspace": "/workspace",
        },
    }


def _write_file(params: Dict[str, Any]) -> Dict[str, Any]:
    path, rel = _resolve_workspace_path(_get_path(params))
    content = str(params.get("content") or params.get("body") or "")

    if not rel.startswith("outbox/"):
        raise SandboxDenied("Docker sandbox only allows file.write under outbox/.")

    if path.exists() and path.is_dir():
        raise SandboxDenied(f"Target is a directory: {rel}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    return {
        "success": True,
        "result": {
            "message": "File written inside Docker sandbox outbox mount.",
            "path": rel,
            "bytes": len(content.encode("utf-8")),
        },
    }


def _send_email(params: Dict[str, Any]) -> Dict[str, Any]:
    to = str(params.get("to") or "").strip()
    if not to:
        raise SandboxDenied("Email recipient is empty.")

    subject = str(params.get("subject") or "AgentGuard Docker Sandbox Mail")
    content = str(params.get("content") or params.get("body") or params.get("message") or "")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    outbox = WORKSPACE / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    mail_path = outbox / f"docker_email_{timestamp}.json"

    record = {
        "to": to,
        "subject": subject,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sandbox_type": "docker",
        "real_external_send": False,
    }
    _write_json(mail_path, record)

    return {
        "success": True,
        "result": {
            "message": "Email was written to Docker sandbox outbox. No real external email was sent.",
            "outbox_file": str(mail_path.relative_to(WORKSPACE)),
            "to": to,
            "subject": subject,
        },
    }


def _run_shell(params: Dict[str, Any]) -> Dict[str, Any]:
    command = str(params.get("command") or params.get("cmd") or "").strip()
    if not command:
        raise SandboxDenied("Shell command is empty.")

    parts = shlex.split(command)
    if not parts:
        raise SandboxDenied("Shell command is empty.")

    command_name = parts[0].lower()
    args = parts[1:]

    if command_name not in SAFE_SHELL_COMMANDS:
        raise SandboxDenied(f"Only safe demo shell commands are allowed: {sorted(SAFE_SHELL_COMMANDS)}")

    if command_name == "echo":
        stdout = " ".join(args)
    elif command_name == "pwd":
        stdout = "/workspace"
    elif command_name == "ls":
        target_raw = args[0] if args else "."
        target, _ = _resolve_workspace_path(target_raw)
        if not target.exists():
            raise SandboxDenied(f"Path does not exist: {target_raw}")
        if target.is_file():
            stdout = target.name
        else:
            stdout = "\n".join(sorted(item.name for item in target.iterdir()))
    elif command_name == "cat":
        if not args:
            raise SandboxDenied("cat requires a file path.")
        return _read_file({"path": args[0]})
    else:
        raise SandboxDenied(f"Command is not implemented: {command_name}")

    return {
        "success": True,
        "result": {
            "command": command,
            "stdout": stdout,
            "stderr": "",
            "cwd": "/workspace",
            "sandbox_interpreter": True,
        },
    }


def execute_tool(tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
    normalized = str(tool or "").strip().lower()

    if normalized == "file.read":
        return _read_file(params)
    if normalized == "file.write":
        return _write_file(params)
    if normalized == "email.send":
        return _send_email(params)
    if normalized == "shell.run":
        return _run_shell(params)

    raise SandboxDenied(f"Tool is not implemented in Docker sandbox runner: {tool}")


def main() -> int:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/sandbox/input.json")
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/sandbox/result.json")

    started_at = datetime.now(timezone.utc).isoformat()

    try:
        request = _read_json(input_path)
        result = execute_tool(
            tool=str(request.get("tool") or ""),
            params=dict(request.get("params") or {}),
        )
        payload = {
            "success": bool(result.get("success")),
            "tool_result": _jsonable(result),
            "error": None,
        }
    except Exception as exc:
        payload = {
            "success": False,
            "tool_result": {
                "success": False,
                "result": str(exc),
            },
            "error": str(exc),
        }

    payload["runner"] = {
        "sandbox_type": "docker",
        "workspace": "/workspace",
        "uid": os.getuid() if hasattr(os, "getuid") else None,
        "gid": os.getgid() if hasattr(os, "getgid") else None,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }

    _write_json(output_path, payload)
    return 0 if payload.get("success") else 2


if __name__ == "__main__":
    raise SystemExit(main())
