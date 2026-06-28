from backend.guardrails.capability_token import verify_capability_token
from backend.research.oauth_comparison import OAuthComparisonRequest, run_oauth_comparison


def test_agentguard_issues_task_scoped_capability_token():
    result = run_oauth_comparison(
        OAuthComparisonRequest(scenario="normal_public_read")
    )

    token_info = result.agentguard["capability_token"]

    assert token_info["token_type"] == "agentguard_capability_token"
    assert token_info["payload"]["type"] == "agentguard_capability_token"

    verified = verify_capability_token(token_info["token"])

    assert verified["valid"] is True
    assert verified["payload"]["capability_contract"]["contract_version"] == "capability_contract_v1"


def test_capability_token_signature_detects_tampering():
    result = run_oauth_comparison(
        OAuthComparisonRequest(scenario="normal_public_read")
    )

    token = result.agentguard["capability_token"]["token"]
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    verified = verify_capability_token(tampered)

    assert verified["valid"] is False
