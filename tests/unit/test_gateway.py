from backend.gateway import check_tool_call
from backend.schemas import ToolCallRequest


def get_decision(result):
    if isinstance(result, dict):
        return result.get("decision")
    return getattr(result, "decision", None)


def check(user: str, tool: str, params: dict):
    request = ToolCallRequest(user=user, tool=tool, params=params)
    return check_tool_call(request)


def test_gateway_allows_public_file_read():
    result = check(
        user="user",
        tool="file.read",
        params={"path": "public/notice.txt"},
    )

    assert get_decision(result) == "allow"


def test_gateway_denies_secret_file_read():
    result = check(
        user="user",
        tool="file.read",
        params={"path": "secret/password.txt"},
    )

    assert get_decision(result) == "deny"


def test_gateway_denies_path_traversal():
    result = check(
        user="user",
        tool="file.read",
        params={"path": "../../secret/password.txt"},
    )

    assert get_decision(result) == "deny"


def test_gateway_requires_confirmation_for_file_delete():
    result = check(
        user="user",
        tool="file.delete",
        params={"path": "public/notice.txt"},
    )

    assert get_decision(result) == "confirm"


def test_gateway_requires_confirmation_for_shell_command():
    result = check(
        user="admin",
        tool="shell.run",
        params={"command": "dir"},
    )

    assert get_decision(result) == "confirm"
