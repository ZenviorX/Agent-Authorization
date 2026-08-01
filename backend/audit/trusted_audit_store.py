from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"

AUDIT_DB_PATH = (
    DATA_DIR
    / "trusted_audit_chain.db"
)

GENESIS_HASH = "0" * 64
CHAIN_HEAD_ID = 1
MAX_TEXT_LENGTH = 500

SENSITIVE_WORDS = {
    "password",
    "passwd",
    "token",
    "secret",
    "credential",
    "api_key",
    "apikey",
    "private_key",
    "??",
    "??",
}


SENSITIVE_IDENTIFIER_KEYS = {
    "approval_ticket",
    "approvalticket",
    "approval_reference",
    "approvalreference",
    "capability_token",
    "capabilitytoken",
    "access_token",
    "accesstoken",
    "refresh_token",
    "refreshtoken",
}


class TrustedAuditError(RuntimeError):
    """Base error for trusted audit storage."""


class TrustedAuditIntegrityError(
    TrustedAuditError
):
    """Audit-chain integrity verification failed."""


def _now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _hash_sensitive_identifier(
    value: Any,
) -> Any:
    """
    Store a stable fingerprint instead of a raw
    approval ticket or authorization token.

    The operation is idempotent: an existing valid
    sha256 fingerprint is returned unchanged.
    """
    if value is None:
        return None

    if isinstance(value, str):
        normalized_string = (
            value.strip()
        )

        if normalized_string.startswith(
            "sha256:"
        ):
            existing_digest = (
                normalized_string[
                    len("sha256:"):
                ]
            )

            if (
                len(existing_digest) == 64
                and all(
                    character
                    in (
                        "0123456789"
                        "abcdefABCDEF"
                    )
                    for character
                    in existing_digest
                )
            ):
                return (
                    "sha256:"
                    + existing_digest.lower()
                )

    if isinstance(
        value,
        (
            dict,
            list,
            tuple,
        ),
    ):
        normalized = _canonical_json(
            value
        )

    else:
        normalized = str(value)

    if not normalized:
        return ""

    digest = hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()

    return "sha256:" + digest


def _sanitize_value(
    key: str,
    value: Any,
) -> Any:
    key_lower = str(key).lower()

    if (
        key_lower
        in SENSITIVE_IDENTIFIER_KEYS
    ):
        return _hash_sensitive_identifier(
            value
        )

    if any(
        word in key_lower
        for word in SENSITIVE_WORDS
    ):
        return "***MASKED***"

    if isinstance(value, dict):
        return {
            str(child_key): _sanitize_value(
                str(child_key),
                child_value,
            )
            for child_key, child_value
            in value.items()
        }

    if isinstance(value, list):
        return [
            _sanitize_value(
                key,
                item,
            )
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            _sanitize_value(
                key,
                item,
            )
            for item in value
        ]

    if isinstance(value, str):
        value_lower = value.lower()

        if any(
            word in value_lower
            for word in SENSITIVE_WORDS
        ):
            return "***MASKED***"

        if len(value) > MAX_TEXT_LENGTH:
            return (
                value[:MAX_TEXT_LENGTH]
                + "...[TRUNCATED]"
            )

        return value

    if value is None:
        return None

    if isinstance(
        value,
        (bool, int, float),
    ):
        return value

    return str(value)


def sanitize_audit_payload(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        str(key): _sanitize_value(
            str(key),
            value,
        )
        for key, value in dict(
            payload or {}
        ).items()
    }


def _record_material(
    *,
    sequence: int,
    event_id: str,
    task_handle: str,
    user: str,
    event_type: str,
    payload_json: str,
    created_at: str,
    prev_hash: str,
) -> Dict[str, Any]:
    return {
        "sequence": int(sequence),
        "event_id": str(event_id),
        "task_handle": str(
            task_handle
        ),
        "user": str(user),
        "event_type": str(
            event_type
        ),
        "payload_json": str(
            payload_json
        ),
        "created_at": str(
            created_at
        ),
        "prev_hash": str(
            prev_hash
        ),
    }


def _calculate_record_hash(
    *,
    sequence: int,
    event_id: str,
    task_handle: str,
    user: str,
    event_type: str,
    payload_json: str,
    created_at: str,
    prev_hash: str,
) -> str:
    material = _record_material(
        sequence=sequence,
        event_id=event_id,
        task_handle=task_handle,
        user=user,
        event_type=event_type,
        payload_json=payload_json,
        created_at=created_at,
        prev_hash=prev_hash,
    )

    encoded = _canonical_json(
        material
    ).encode("utf-8")

    return hashlib.sha256(
        encoded
    ).hexdigest()


def connect() -> sqlite3.Connection:
    AUDIT_DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        AUDIT_DB_PATH,
        timeout=30,
        isolation_level=None,
    )

    connection.row_factory = (
        sqlite3.Row
    )

    connection.execute(
        "PRAGMA journal_mode=WAL"
    )

    connection.execute(
        "PRAGMA synchronous=FULL"
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS
        trusted_audit_events (
            sequence INTEGER PRIMARY KEY,
            event_id TEXT NOT NULL UNIQUE,
            task_handle TEXT NOT NULL,
            user TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            prev_hash TEXT NOT NULL,
            record_hash TEXT NOT NULL UNIQUE
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_trusted_audit_task
        ON trusted_audit_events(
            task_handle,
            sequence
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_trusted_audit_type
        ON trusted_audit_events(
            event_type,
            sequence
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS
        trusted_audit_head (
            head_id INTEGER PRIMARY KEY,
            last_sequence INTEGER NOT NULL,
            last_hash TEXT NOT NULL,
            total_records INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        INSERT OR IGNORE INTO
        trusted_audit_head (
            head_id,
            last_sequence,
            last_hash,
            total_records,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            CHAIN_HEAD_ID,
            0,
            GENESIS_HASH,
            0,
            _now_iso(),
        ),
    )

    return connection


def append_trusted_audit_event(
    *,
    task_handle: str,
    user: str,
    event_type: str,
    payload: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:
    task_handle = str(
        task_handle
    ).strip()

    user = str(user).strip()

    event_type = str(
        event_type
    ).strip()

    if not task_handle:
        raise ValueError(
            "task_handle is required"
        )

    if not user:
        raise ValueError(
            "user is required"
        )

    if not event_type:
        raise ValueError(
            "event_type is required"
        )

    sanitized_payload = (
        sanitize_audit_payload(
            dict(payload or {})
        )
    )

    payload_json = _canonical_json(
        sanitized_payload
    )

    event_id = (
        "aud_"
        + secrets.token_urlsafe(24)
    )

    created_at = _now_iso()

    connection = connect()

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        head = connection.execute(
            """
            SELECT
                last_sequence,
                last_hash,
                total_records
            FROM trusted_audit_head
            WHERE head_id = ?
            """,
            (CHAIN_HEAD_ID,),
        ).fetchone()

        if head is None:
            raise TrustedAuditError(
                "Audit chain head is missing"
            )

        sequence = int(
            head["last_sequence"]
        ) + 1

        prev_hash = str(
            head["last_hash"]
        )

        record_hash = (
            _calculate_record_hash(
                sequence=sequence,
                event_id=event_id,
                task_handle=task_handle,
                user=user,
                event_type=event_type,
                payload_json=(
                    payload_json
                ),
                created_at=created_at,
                prev_hash=prev_hash,
            )
        )

        connection.execute(
            """
            INSERT INTO
            trusted_audit_events (
                sequence,
                event_id,
                task_handle,
                user,
                event_type,
                payload_json,
                created_at,
                prev_hash,
                record_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sequence,
                event_id,
                task_handle,
                user,
                event_type,
                payload_json,
                created_at,
                prev_hash,
                record_hash,
            ),
        )

        connection.execute(
            """
            UPDATE trusted_audit_head
            SET
                last_sequence = ?,
                last_hash = ?,
                total_records = ?,
                updated_at = ?
            WHERE head_id = ?
            """,
            (
                sequence,
                record_hash,
                int(
                    head[
                        "total_records"
                    ]
                )
                + 1,
                created_at,
                CHAIN_HEAD_ID,
            ),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return {
        "sequence": sequence,
        "event_id": event_id,
        "task_handle": (
            task_handle
        ),
        "user": user,
        "event_type": event_type,
        "payload": sanitized_payload,
        "created_at": created_at,
        "prev_hash": prev_hash,
        "record_hash": record_hash,
    }


def get_trusted_audit_events(
    *,
    task_handle: Optional[
        str
    ] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    normalized_limit = max(
        1,
        min(int(limit), 1000),
    )

    connection = connect()

    try:
        if task_handle:
            rows = connection.execute(
                """
                SELECT
                    sequence,
                    event_id,
                    task_handle,
                    user,
                    event_type,
                    payload_json,
                    created_at,
                    prev_hash,
                    record_hash
                FROM trusted_audit_events
                WHERE task_handle = ?
                ORDER BY sequence ASC
                LIMIT ?
                """,
                (
                    str(
                        task_handle
                    ).strip(),
                    normalized_limit,
                ),
            ).fetchall()

        else:
            rows = connection.execute(
                """
                SELECT
                    sequence,
                    event_id,
                    task_handle,
                    user,
                    event_type,
                    payload_json,
                    created_at,
                    prev_hash,
                    record_hash
                FROM trusted_audit_events
                ORDER BY sequence DESC
                LIMIT ?
                """,
                (
                    normalized_limit,
                ),
            ).fetchall()

            rows = list(
                reversed(rows)
            )

        result: List[
            Dict[str, Any]
        ] = []

        for row in rows:
            try:
                payload = json.loads(
                    row["payload_json"]
                )
            except json.JSONDecodeError:
                payload = {
                    "_corrupted": True,
                    "_raw": str(
                        row[
                            "payload_json"
                        ]
                    ),
                }

            result.append(
                {
                    "sequence": int(
                        row["sequence"]
                    ),
                    "event_id": str(
                        row["event_id"]
                    ),
                    "task_handle": str(
                        row[
                            "task_handle"
                        ]
                    ),
                    "user": str(
                        row["user"]
                    ),
                    "event_type": str(
                        row["event_type"]
                    ),
                    "payload": payload,
                    "created_at": str(
                        row["created_at"]
                    ),
                    "prev_hash": str(
                        row["prev_hash"]
                    ),
                    "record_hash": str(
                        row["record_hash"]
                    ),
                }
            )

        return result

    finally:
        connection.close()


def verify_trusted_audit_chain(
) -> Dict[str, Any]:
    connection = connect()

    try:
        head = connection.execute(
            """
            SELECT
                last_sequence,
                last_hash,
                total_records,
                updated_at
            FROM trusted_audit_head
            WHERE head_id = ?
            """,
            (CHAIN_HEAD_ID,),
        ).fetchone()

        rows = connection.execute(
            """
            SELECT
                sequence,
                event_id,
                task_handle,
                user,
                event_type,
                payload_json,
                created_at,
                prev_hash,
                record_hash
            FROM trusted_audit_events
            ORDER BY sequence ASC
            """
        ).fetchall()

    finally:
        connection.close()

    if head is None:
        return {
            "valid": False,
            "checked_records": 0,
            "broken_sequence": None,
            "reason": (
                "Audit chain head is missing."
            ),
        }

    head_total = int(
        head["total_records"]
    )

    if len(rows) != head_total:
        return {
            "valid": False,
            "checked_records": 0,
            "broken_sequence": None,
            "reason": (
                "Stored record count does not "
                "match the trusted chain head. "
                "Records may have been deleted "
                "or inserted."
            ),
            "expected_records": (
                head_total
            ),
            "actual_records": len(rows),
        }

    previous_hash = GENESIS_HASH
    checked_records = 0

    for row in rows:
        sequence = int(
            row["sequence"]
        )

        prev_hash = str(
            row["prev_hash"]
        )

        record_hash = str(
            row["record_hash"]
        )

        if prev_hash != previous_hash:
            return {
                "valid": False,
                "checked_records": (
                    checked_records
                ),
                "broken_sequence": (
                    sequence
                ),
                "reason": (
                    "prev_hash does not match "
                    "the preceding record."
                ),
            }

        payload_json = str(
            row["payload_json"]
        )

        try:
            parsed_payload = (
                json.loads(
                    payload_json
                )
            )

        except json.JSONDecodeError:
            return {
                "valid": False,
                "checked_records": (
                    checked_records
                ),
                "broken_sequence": (
                    sequence
                ),
                "reason": (
                    "payload_json is not "
                    "valid JSON."
                ),
            }

        if (
            _canonical_json(
                parsed_payload
            )
            != payload_json
        ):
            return {
                "valid": False,
                "checked_records": (
                    checked_records
                ),
                "broken_sequence": (
                    sequence
                ),
                "reason": (
                    "payload_json is not in "
                    "canonical form."
                ),
            }

        recalculated = (
            _calculate_record_hash(
                sequence=sequence,
                event_id=str(
                    row["event_id"]
                ),
                task_handle=str(
                    row["task_handle"]
                ),
                user=str(row["user"]),
                event_type=str(
                    row["event_type"]
                ),
                payload_json=(
                    payload_json
                ),
                created_at=str(
                    row["created_at"]
                ),
                prev_hash=prev_hash,
            )
        )

        if recalculated != record_hash:
            return {
                "valid": False,
                "checked_records": (
                    checked_records
                ),
                "broken_sequence": (
                    sequence
                ),
                "reason": (
                    "record_hash verification "
                    "failed. The audit record "
                    "may have been modified."
                ),
            }

        previous_hash = record_hash
        checked_records += 1

    if rows:
        actual_last_sequence = int(
            rows[-1]["sequence"]
        )

        actual_last_hash = str(
            rows[-1]["record_hash"]
        )

    else:
        actual_last_sequence = 0
        actual_last_hash = (
            GENESIS_HASH
        )

    if (
        actual_last_sequence
        != int(
            head["last_sequence"]
        )
        or actual_last_hash
        != str(head["last_hash"])
    ):
        return {
            "valid": False,
            "checked_records": (
                checked_records
            ),
            "broken_sequence": (
                actual_last_sequence
                or None
            ),
            "reason": (
                "The final audit record does "
                "not match the trusted chain "
                "head. Tail records may have "
                "been deleted or replaced."
            ),
        }

    return {
        "valid": True,
        "checked_records": (
            checked_records
        ),
        "broken_sequence": None,
        "total_records": head_total,
        "last_sequence": int(
            head["last_sequence"]
        ),
        "last_hash": str(
            head["last_hash"]
        ),
        "reason": (
            "Trusted audit chain "
            "verification passed."
        ),
    }
