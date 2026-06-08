import json
from pathlib import Path

import pytest

import backend.gateway.gateway as gateway_module
from backend.gateway.semantic_guard import clear_semantic_cache
from backend.schemas import ToolCallRequest


CASE_PATH = Path("security_cases/gateway_cases_v4.json")


def _load_cases():
    data = json.loads(CASE_PATH.read_text(encoding="utf-8-sig"))
    assert isinstance(data, list)
    return data


@pytest.fixture(autouse=True)
def enable_real_semantic_guard(monkeypatch):
    """
    v4 安全样例需要真实启用 Embedding 语义检测。
    首次运行会下载 semantic_guard.yaml 中配置的本地模型。
    """
    monkeypatch.setenv("SEMANTIC_GUARD_ENABLED", "true")
    clear_semantic_cache()
    yield
    clear_semantic_cache()


@pytest.mark.parametrize("case", _load_cases(), ids=lambda item: item["id"])
def test_gateway_v4_security_cases(case):
    request_data = dict(case["request"])
    request = ToolCallRequest(**request_data)

    result = gateway_module.check_tool_call(request)

    if "expected_decision" in case:
        assert result["decision"] == case["expected_decision"], result

    if "expected_decision_in" in case:
        assert result["decision"] in case["expected_decision_in"], result

    expected_labels = set(case.get("expected_semantic_labels", []))
    if expected_labels:
        semantic_guard = result.get("semantic_guard", {})
        assert semantic_guard.get("enabled") is True, result
        assert semantic_guard.get("risk_score", 0) > 0, result

        actual_labels = set(semantic_guard.get("labels", []))
        assert actual_labels & expected_labels, {
            "case_id": case["id"],
            "expected_any_label": sorted(expected_labels),
            "actual_labels": sorted(actual_labels),
            "semantic_guard": semantic_guard,
            "decision": result.get("decision"),
            "reason": result.get("reason"),
        }
