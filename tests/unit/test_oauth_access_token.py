from backend.oauth.token_service import issue_access_token, verify_access_token


def test_demo_access_token_round_trip():
    issued = issue_access_token(
        subject="alice",
        scopes=["mcp:tools:list", "tool:file:read"],
        audience="http://127.0.0.1:8000/mcp",
        issuer="http://127.0.0.1:9000",
        client_id="test-client",
        ttl_seconds=600,
    )

    verified = verify_access_token(
        issued["access_token"],
        expected_audience="http://127.0.0.1:8000/mcp",
        expected_issuer="http://127.0.0.1:9000",
    )

    assert verified["valid"] is True
    assert verified["payload"]["sub"] == "alice"
    assert verified["payload"]["client_id"] == "test-client"
    assert verified["payload"]["scopes"] == ["mcp:tools:list", "tool:file:read"]


def test_demo_access_token_rejects_wrong_audience():
    issued = issue_access_token(
        subject="alice",
        scopes=["mcp:tools:list"],
        audience="http://127.0.0.1:8000/mcp",
        issuer="http://127.0.0.1:9000",
    )

    verified = verify_access_token(
        issued["access_token"],
        expected_audience="http://127.0.0.1:9999/mcp",
        expected_issuer="http://127.0.0.1:9000",
    )

    assert verified["valid"] is False
    assert verified["error"] == "invalid_audience"


def test_demo_access_token_rejects_tampering():
    issued = issue_access_token(
        subject="alice",
        scopes=["mcp:tools:list"],
    )
    token = issued["access_token"]
    replacement = "A" if token[-1] != "A" else "B"

    verified = verify_access_token(token[:-1] + replacement)

    assert verified["valid"] is False
    assert verified["error"] == "invalid_signature"
