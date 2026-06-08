"""
Small security detector helpers used by the Gateway.

These functions are intentionally pure and configuration-independent. They
classify already-matched keywords into higher-level hard-risk categories.
"""

from __future__ import annotations


def is_path_bypass_keyword(keyword: str) -> bool:
    """
    Return True if a matched path keyword indicates traversal or encoded bypass.

    These hits should be treated as hard-deny signals, not only as risk-score
    increments.
    """
    normalized = str(keyword).lower().replace("\\", "/")
    bypass_markers = (
        "../",
        "%2e%2e",
        "%252e%252e",
        "%2f",
        "%5c",
        "%252f",
        "%255c",
        "....//",
        "..././",
    )
    return any(marker in normalized for marker in bypass_markers)


def is_destructive_sql_keyword(keyword: str) -> bool:
    """
    Return True if a SQL keyword represents destructive or privilege-changing SQL.

    These operations should remain deny even for high-privilege users.
    """
    normalized = str(keyword).lower().strip()
    destructive_markers = (
        "drop",
        "truncate",
        "delete",
        "update",
        "insert",
        "alter",
        "grant",
        "revoke",
        "xp_cmdshell",
        "outfile",
        "load_file",
        "load_extension",
    )
    return any(marker in normalized for marker in destructive_markers)


# Backward-compatible private aliases for minimal gateway.py edits.
_is_path_bypass_keyword = is_path_bypass_keyword
_is_destructive_sql_keyword = is_destructive_sql_keyword
