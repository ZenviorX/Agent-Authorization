import json
from pathlib import Path

import pytest

from backend.gateway import check_tool_call
from backend.schemas import ToolCallRequest


CASE_DIR = Path("security_cases")


def get_decision(result):
    if isinstance(result, dict):
        return result.get("decision")
    return getattr(result, "decision", None)


def load_gateway_cases():
    cases = []

    if not CASE_DIR.exists():
        return cases

    for file_path in sorted(CASE_DIR.glob("gateway_cases*.json")):
        data = json.loads(file_path.read_text(encoding="utf-8"))

        if isinstance(data, dict) and "cases" in data:
            data = data["cases"]

        if not isinstance(data, list):
            continue

        for case in data:
            if not isinstance(case, dict):
                continue

            if "request" not in case:
                continue

            if "expected_decision" not in case and "expected_decision_in" not in case:
                continue

            case["_source_file"] = file_path.name
            cases.append(case)

    return cases


@pytest.mark.parametrize(
    "case",
    load_gateway_cases(),
    ids=lambda case: case.get("id", case.get("_source_file", "case")),
)
def test_gateway_redteam_cases(case):
    request = ToolCallRequest(**case["request"])
    result = check_tool_call(request)
    decision = get_decision(result)

    expected = case.get("expected_decision")
    expected_in = case.get("expected_decision_in")

    if expected_in is not None:
        assert decision in expected_in, (
            f"{case.get('id')} from {case.get('_source_file')} expected one of "
            f"{expected_in}, got {decision}. result={result}"
        )
    else:
        assert decision == expected, (
            f"{case.get('id')} from {case.get('_source_file')} expected "
            f"{expected}, got {decision}. result={result}"
        )