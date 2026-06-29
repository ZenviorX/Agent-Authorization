from pathlib import Path

from backend.sandbox.native_sandbox_executor import execute_tool_in_native_sandbox
from backend.tools.tool_executor import ensure_sandbox_ready


def test_native_sandbox_can_read_public_file():
    ensure_sandbox_ready()
    result = execute_tool_in_native_sandbox(
        tool="file.read",
        params={"path": "public/notice.txt"},
        profile_name="local_readonly",
    )

    assert result["success"] is True
    assert result["sandbox_evidence"]["sandbox_type"] == "native_subprocess"
    assert result["sandbox_evidence"]["tool_result"]["success"] is True


def test_native_sandbox_blocks_secret_file_under_strict_profile():
    ensure_sandbox_ready()
    result = execute_tool_in_native_sandbox(
        tool="file.read",
        params={"path": "secret/password.txt"},
        profile_name="strict",
    )

    assert result["success"] is False
    assert result["sandbox_evidence"]["sandbox_type"] == "native_subprocess"
    assert "outside allowed native sandbox prefixes" in str(result["result"])


def test_native_sandbox_allows_outbox_write_only_for_safe_write_profile():
    ensure_sandbox_ready()
    result = execute_tool_in_native_sandbox(
        tool="file.write",
        params={"path": "outbox/native_demo.txt", "content": "hello native sandbox"},
        profile_name="local_safe_write",
    )

    assert result["success"] is True
    assert result["sandbox_evidence"]["tool_result"]["success"] is True
