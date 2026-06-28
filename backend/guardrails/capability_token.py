from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set

from backend.guardrails.capability_token_ledger import get_token_status, record_token_consumed, record_token_issued


DEFAULT_SECRET = "agentguard-dev-capability-secret"
_CONSUMED_TOKEN_IDS: Set[str] = set()


def _secret() -> bytes:
    return os.getenv("AGENTGUARD_CAPABILITY_SECRET", DEFAULT_SECRET).encode("utf-8")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _json_b64(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _b64(raw)




def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value or {},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]

def _sign(data: str) -> str:
    digest = hmac.new(_secret(), data.encode("utf-8"), hashlib.sha256).digest()
    return _b64(digest)


def issue_capability_token(
    user: str,
    agent_platform: str,
    original_task: str,
    capability_contract: Dict[str, Any],
    tool: str = "",
    params: Optional[Dict[str, Any]] = None,
    sandbox_profile: str = "",
    ttl_minutes: int = 15,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ttl_minutes)

    payload = {
        "type": "agentguard_capability_token",
        "version": "v1",
        "token_id": hashlib.sha256(
            f"{user}:{agent_platform}:{original_task}:{tool}:{_stable_hash(params or {})}:{now.isoformat()}".encode("utf-8")
        ).hexdigest()[:16],
        "user": user,
        "agent_platform": agent_platform,
        "task_hash": hashlib.sha256(original_task.encode("utf-8")).hexdigest()[:16],
        "tool": tool,
        "params_hash": _stable_hash(params or {}),
        "sandbox_profile": sandbox_profile,
        "capability_contract": capability_contract,
        "issued_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    payload_part = _json_b64(payload)
    signature = _sign(payload_part)
    token = f"{payload_part}.{signature}"

    record_token_issued(str(payload.get("token_id", "")), payload)

    return {
        "token_type": "agentguard_capability_token",
        "token": token,
        "payload": payload,
    }


def verify_capability_token(token: str) -> Dict[str, Any]:
    try:
        payload_part, signature = token.split(".", 1)
    except ValueError:
        return {"valid": False, "reason": "Malformed capability token."}

    expected = _sign(payload_part)
    if not hmac.compare_digest(signature, expected):
        return {"valid": False, "reason": "Invalid capability token signature."}

    padded = payload_part + "=" * (-len(payload_part) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))

    expires_at = datetime.fromisoformat(payload["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        return {"valid": False, "reason": "Capability token expired.", "payload": payload}

    return {"valid": True, "reason": "Capability token is valid.", "payload": payload}

def validate_capability_token_for_request(
    token: str,
    user: str,
    agent_platform: str,
    original_task: str,
    expected_contract: Dict[str, Any],
    tool: str = "",
    params: Optional[Dict[str, Any]] = None,
    sandbox_profile: str = "",
    require_token: bool = False,
) -> Dict[str, Any]:
    if not token:
        if require_token:
            return {
                "provided": False,
                "decision": "deny",
                "risk_delta": 100,
                "reason": ["Execution request must provide a valid task-scoped capability token."],
            }

        return {
            "provided": False,
            "decision": "allow",
            "risk_delta": 0,
            "ledger_status": "not_provided",
            "reason": ["No capability token provided; this request is treated as an initial authorization request."],
        }

    verified = verify_capability_token(token)
    if not verified.get("valid"):
        return {
            "provided": True,
            "decision": "deny",
            "risk_delta": 100,
            "ledger_status": "invalid",
            "reason": [verified.get("reason", "Invalid capability token.")],
        }

    payload = verified["payload"]
    expected_task_hash = hashlib.sha256(original_task.encode("utf-8")).hexdigest()[:16]

    reasons = ["Capability token signature and expiry were verified."]

    token_id = str(payload.get("token_id", ""))
    if require_token and token_id in _CONSUMED_TOKEN_IDS:
        return {
            "provided": True,
            "decision": "deny",
            "risk_delta": 100,
            "ledger_status": "consumed",
            "reason": reasons + ["Capability token has already been consumed."],
        }

    ledger_status = get_token_status(token_id)
    ledger_state = ledger_status.get("status", "unknown")

    if require_token and ledger_status.get("status") == "revoked":
        return {
            "provided": True,
            "decision": "deny",
            "risk_delta": 100,
            "ledger_status": "revoked",
            "reason": reasons + ["Capability token has been revoked."],
        }

    if payload.get("user") != user:
        return {
            "provided": True,
            "decision": "deny",
            "risk_delta": 100,
            "ledger_status": ledger_state,
            "reason": reasons + ["Capability token user does not match current request user."],
        }

    if payload.get("agent_platform") != agent_platform:
        return {
            "provided": True,
            "decision": "deny",
            "risk_delta": 100,
            "ledger_status": ledger_state,
            "reason": reasons + ["Capability token agent platform does not match current request."],
        }

    if payload.get("task_hash") != expected_task_hash:
        return {
            "provided": True,
            "decision": "deny",
            "risk_delta": 100,
            "ledger_status": ledger_state,
            "reason": reasons + ["Capability token is bound to a different original task."],
        }

    if payload.get("tool", "") != tool:
        return {
            "provided": True,
            "decision": "deny",
            "risk_delta": 100,
            "ledger_status": ledger_state,
            "reason": reasons + ["Capability token is bound to a different tool."],
        }

    if payload.get("params_hash", "") != _stable_hash(params or {}):
        return {
            "provided": True,
            "decision": "deny",
            "risk_delta": 100,
            "ledger_status": ledger_state,
            "reason": reasons + ["Capability token is bound to different tool parameters."],
        }

    if payload.get("sandbox_profile", "") != sandbox_profile:
        return {
            "provided": True,
            "decision": "deny",
            "risk_delta": 100,
            "ledger_status": ledger_state,
            "reason": reasons + ["Capability token is bound to a different sandbox profile."],
        }

    if payload.get("capability_contract") != expected_contract:
        return {
            "provided": True,
            "decision": "deny",
            "risk_delta": 100,
            "ledger_status": ledger_state,
            "reason": reasons + ["Capability token contract does not match current derived contract."],
        }

    return {
        "provided": True,
        "decision": "allow",
        "risk_delta": 0,
        "ledger_status": ledger_state,
        "reason": reasons + ["Capability token matches current task, user, agent and contract."],
    }



def mark_capability_token_consumed(token: str) -> Dict[str, Any]:
    verified = verify_capability_token(token)
    if not verified.get("valid"):
        return {
            "consumed": False,
            "reason": verified.get("reason", "Invalid capability token."),
        }

    payload = verified.get("payload", {})
    token_id = str(payload.get("token_id", ""))

    if not token_id:
        return {
            "consumed": False,
            "reason": "Capability token does not contain token_id.",
        }

    _CONSUMED_TOKEN_IDS.add(token_id)
    record_token_consumed(token_id)

    return {
        "consumed": True,
        "token_id": token_id,
        "reason": "Capability token consumed after successful execution.",
    }
