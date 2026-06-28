from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
LEDGER_DIR = ROOT / "runtime_workspace"
LEDGER_DB = LEDGER_DIR / "capability_token_ledger.db"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(LEDGER_DB)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS capability_tokens (
            token_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            issued_at TEXT,
            consumed_at TEXT,
            revoked_at TEXT,
            revoke_reason TEXT,
            payload_json TEXT
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS capability_token_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_id TEXT NOT NULL,
            event TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            detail_json TEXT
        )
        """
    )

    conn.commit()


def _record_event(
    conn: sqlite3.Connection,
    token_id: str,
    event: str,
    detail: Dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO capability_token_events(token_id, event, timestamp, detail_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            token_id,
            event,
            _now(),
            json.dumps(detail or {}, ensure_ascii=False),
        ),
    )


def record_token_issued(token_id: str, payload: Dict[str, Any]) -> None:
    if not token_id:
        return

    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO capability_tokens(
                token_id,
                status,
                issued_at,
                consumed_at,
                revoked_at,
                revoke_reason,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id,
                "issued",
                _now(),
                None,
                None,
                "",
                json.dumps(payload, ensure_ascii=False),
            ),
        )

        _record_event(
            conn,
            token_id,
            "issued",
            {"agent_platform": payload.get("agent_platform", "")},
        )

        conn.commit()


def record_token_consumed(token_id: str) -> None:
    if not token_id:
        return

    with _connect() as conn:
        existing = conn.execute(
            "SELECT token_id FROM capability_tokens WHERE token_id = ?",
            (token_id,),
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE capability_tokens
                SET status = ?, consumed_at = ?
                WHERE token_id = ?
                """,
                ("consumed", _now(), token_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO capability_tokens(
                    token_id,
                    status,
                    issued_at,
                    consumed_at,
                    revoked_at,
                    revoke_reason,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token_id,
                    "consumed",
                    None,
                    _now(),
                    None,
                    "",
                    "{}",
                ),
            )

        _record_event(conn, token_id, "consumed")
        conn.commit()


def record_token_revoked(token_id: str, reason: str = "") -> None:
    if not token_id:
        return

    with _connect() as conn:
        existing = conn.execute(
            "SELECT token_id FROM capability_tokens WHERE token_id = ?",
            (token_id,),
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE capability_tokens
                SET status = ?, revoked_at = ?, revoke_reason = ?
                WHERE token_id = ?
                """,
                ("revoked", _now(), reason, token_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO capability_tokens(
                    token_id,
                    status,
                    issued_at,
                    consumed_at,
                    revoked_at,
                    revoke_reason,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token_id,
                    "revoked",
                    None,
                    None,
                    _now(),
                    reason,
                    "{}",
                ),
            )

        _record_event(conn, token_id, "revoked", {"reason": reason})
        conn.commit()


def get_token_status(token_id: str) -> Dict[str, Any]:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT token_id, status, issued_at, consumed_at, revoked_at, revoke_reason, payload_json
            FROM capability_tokens
            WHERE token_id = ?
            """,
            (token_id,),
        ).fetchone()

    if not row:
        return {
            "token_id": token_id,
            "status": "unknown",
            "issued_at": None,
            "consumed_at": None,
            "revoked_at": None,
            "revoke_reason": "",
            "payload": {},
        }

    payload_text = row["payload_json"] or "{}"

    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        payload = {}

    return {
        "token_id": row["token_id"],
        "status": row["status"],
        "issued_at": row["issued_at"],
        "consumed_at": row["consumed_at"],
        "revoked_at": row["revoked_at"],
        "revoke_reason": row["revoke_reason"] or "",
        "payload": payload,
    }


def get_token_events(token_id: str = "") -> List[Dict[str, Any]]:
    with _connect() as conn:
        if token_id:
            rows = conn.execute(
                """
                SELECT token_id, event, timestamp, detail_json
                FROM capability_token_events
                WHERE token_id = ?
                ORDER BY id ASC
                """,
                (token_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT token_id, event, timestamp, detail_json
                FROM capability_token_events
                ORDER BY id ASC
                """
            ).fetchall()

    events: List[Dict[str, Any]] = []

    for row in rows:
        try:
            detail = json.loads(row["detail_json"] or "{}")
        except json.JSONDecodeError:
            detail = {}

        events.append({
            "token_id": row["token_id"],
            "event": row["event"],
            "timestamp": row["timestamp"],
            "detail": detail,
        })

    return events


def reset_token_ledger() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM capability_token_events")
        conn.execute("DELETE FROM capability_tokens")
        conn.commit()
