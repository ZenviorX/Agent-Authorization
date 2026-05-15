import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "audit.log"
SENSITIVE_WORDS = ["password", "token", "secret", "key", "credential", "密钥", "密码"]
MAX_LOG_VALUE_LENGTH = 500


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _mask_sensitive_value(key: str, value: Any):
    """
    简单脱敏，避免日志里直接保存 password、token、key 等敏感值。
    """
    key_lower = str(key).lower()

    if any(word in key_lower for word in SENSITIVE_WORDS):
        return "***MASKED***"

    if isinstance(value, dict):
        return {k: _mask_sensitive_value(k, v) for k, v in value.items()}

    if isinstance(value, list):
        return [_mask_sensitive_value(key, item) for item in value]

    if isinstance(value, str):
        value_lower = value.lower()
        if any(word in value_lower for word in SENSITIVE_WORDS):
            return "***MASKED***"

        if len(value) > MAX_LOG_VALUE_LENGTH:
            return value[:MAX_LOG_VALUE_LENGTH] + "...[TRUNCATED]"

    return value


def _mask_log_value(value: Any):
    return _mask_sensitive_value("", value)


def write_log(
    user: str,
    tool: str,
    params: Dict[str, Any],
    gateway_result: Dict[str, Any],
    executed: bool,
    original_input: Optional[str] = None,
    message: Optional[str] = None,
    pending_id: Optional[str] = None,
    tool_result: Optional[Dict[str, Any]] = None,
):
    """
    写入一条审计日志。
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    record = {
        "request_id": str(uuid4()),
        "time": _now(),
        "user": user,
        "original_input": _mask_log_value(original_input),
        "tool": tool,
        "params": _mask_log_value(params),
        "decision": gateway_result.get("decision"),
        "risk_score": gateway_result.get("risk_score"),
        "reason": gateway_result.get("reason"),
        "executed": executed,
        "pending_id": pending_id,
        "message": _mask_log_value(message),
        "tool_result": _mask_log_value(tool_result),
    }

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def get_logs(limit: int = 50):
    """
    读取最近 limit 条审计日志。
    """
    if not LOG_FILE.exists():
        return []

    lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
    lines = lines[-limit:]

    logs = []
    for line in lines:
        try:
            logs.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return logs[::-1]
