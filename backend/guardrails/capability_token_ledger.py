from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

_TOKEN_LEDGER: Dict[str, Dict[str, Any]] = {}
_TOKEN_EVENTS: List[Dict[str, Any]] = []


def _record_event(token_id: str, event: str, detail: Dict[str, Any] | None = None) -> None:
    _TOKEN_EVENTS.append({
        "token_id": token_id,
        "event": event,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "detail": detail or {},
    })


def record_token_issued(token_id: str, payload: Dict[str, Any]) -> None:
    if not token_id:
        return

    _TOKEN_LEDGER[token_id] = {
        "token_id": token_id,
        "status": "issued",
        "issued_at": datetime.now().isoformat(timespec="seconds"),
        "consumed_at": None,
        "revoked_at": None,
        "revoke_reason": "",
        "payload": payload,
    }

    _record_event(token_id, "issued", {"agent_platform": payload.get("agent_platform", "")})


def record_token_consumed(token_id: str) -> None:
    if not token_id:
        return

    item = _TOKEN_LEDGER.get(token_id)
    if item:
        item["status"] = "consumed"
        item["consumed_at"] = datetime.now().isoformat(timespec="seconds")
        _record_event(token_id, "consumed")
    else:
        _TOKEN_LEDGER[token_id] = {
            "token_id": token_id,
            "status": "consumed",
            "issued_at": None,
            "consumed_at": datetime.now().isoformat(timespec="seconds"),
            "payload": {},
        }


def get_token_status(token_id: str) -> Dict[str, Any]:
    return _TOKEN_LEDGER.get(token_id, {
        "token_id": token_id,
        "status": "unknown",
        "issued_at": None,
        "consumed_at": None,
        "payload": {},
    })


def reset_token_ledger() -> None:
    _TOKEN_LEDGER.clear()
    _TOKEN_EVENTS.clear()



def record_token_revoked(token_id: str, reason: str = "") -> None:
    if not token_id:
        return

    item = _TOKEN_LEDGER.get(token_id)
    if item:
        item["status"] = "revoked"
        item["revoked_at"] = datetime.now().isoformat(timespec="seconds")
        item["revoke_reason"] = reason
        _record_event(token_id, "revoked", {"reason": reason})
    else:
        _TOKEN_LEDGER[token_id] = {
            "token_id": token_id,
            "status": "revoked",
            "issued_at": None,
            "consumed_at": None,
            "revoked_at": datetime.now().isoformat(timespec="seconds"),
            "revoke_reason": reason,
            "payload": {},
        }



def get_token_events(token_id: str = "") -> List[Dict[str, Any]]:
    if not token_id:
        return list(_TOKEN_EVENTS)
    return [event for event in _TOKEN_EVENTS if event.get("token_id") == token_id]
