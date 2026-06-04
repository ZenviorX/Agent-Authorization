from backend.schemas import ToolCallRequest
from backend.gateway.gateway import check_tool_call


def test_unknown_tool_is_denied():
    result = check_tool_call(
        ToolCallRequest(
            user="student",
            tool="camera.capture",
            params={},
        )
    )

    assert result["decision"] == "deny"


def test_low_confidence_is_denied():
    result = check_tool_call(
        ToolCallRequest(
            user="student",
            tool="file.read",
            params={"path": "public/notice.txt"},
            agent_confidence=0.3,
        )
    )

    assert result["decision"] == "deny"


def test_missing_param_requires_confirm():
    result = check_tool_call(
        ToolCallRequest(
            user="student",
            tool="email.send",
            params={"to": "unknown", "content": ""},
            agent_confidence=0.9,
        )
    )

    assert result["decision"] == "confirm"
