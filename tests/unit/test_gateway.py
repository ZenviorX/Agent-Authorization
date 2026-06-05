from backend.gateway import check_tool_call
from backend.schemas import ToolCallRequest


def check(user: str, tool: str, params: dict, **extra):
    request = ToolCallRequest(user=user, tool=tool, params=params, **extra)
    return check_tool_call(request)


def test_public_file_read_is_allowed_for_student():
    result = check("student", "file.read", {"path": "public/notice.txt"})
    assert result["decision"] == "allow"


def test_secret