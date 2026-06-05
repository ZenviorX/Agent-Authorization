from backend.gateway import check_tool_call
from backend.schemas import ToolCallRequest


def test_gateway_core_decisions():
    cases = [
        ("student", "file.read", {"path": "public/notice.txt"}, "allow"),
        ("student", "file.read", {"path": "secret/password.txt"}, "deny"),
        ("alice", "file.delete", {"path": "public/notice.txt"}, "confirm"),