from backend.proxy.proxy_models import ToolProxyAuthorizeRequest
from backend.proxy.tool_proxy_service import authorize_tool_call


def test_execute_request_without_capability_token_is_denied():
    request = ToolProxyAuthorizeRequest(
        user="user",
        original_task="请读取 public/notice.txt 并总结",
        tool="file.read",
        params={"path": "public/notice.txt"},
        requested_scopes=["tool:file:read"],
        oauth_token_claims={"scope": "tool:file:read"},
        auth_mode="oauth_scope",
        agent_platform="openclaw",
        sandbox_profile="local_readonly",
        execute=True,
        capability_token="",
    )

    result = authorize_tool_call(request)

    assert result.decision == "deny"
    assert result.executed is False

    token_stage = next(
        item for item in result.authorization_trace
        if item["stage"] == "capability_token"
    )

    assert token_stage["decision"] == "deny"
    assert token_stage["extra"]["provided"] is False
