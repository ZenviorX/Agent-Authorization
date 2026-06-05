from backend.gateway import check_tool_call
from backend.schemas import ToolCallRequest


def test_public_read_allowed():
    req = ToolCallRequest(user="student", tool="file.read", params={"path": "public/notice.txt"})
    assert check_tool_call(req)["decision"] == "allow"
