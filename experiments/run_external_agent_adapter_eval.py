from __future__ import annotations

import sys
from pathlib import Path as _Path

PROJECT_ROOT = _Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from backend.adapters.external_agent_adapter import (
    ExternalAgentSimulateRequest,
    simulate_external_agent_call,
)


def _next_result_path() -> Path:
    results_dir = Path("Results")
    results_dir.mkdir(parents=True, exist_ok=True)

    max_number = 0

    for path in results_dir.glob("Result_*.json"):
        stem = path.stem
        if not stem.startswith("Result_"):
            continue

        number_part = stem.replace("Result_", "", 1)

        if number_part.isdigit():
            max_number = max(max_number, int(number_part))

    return results_dir / f"Result_{max_number + 1:03d}.json"


def _safe_get(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = data

    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)

    return current if current is not None else default


def _run_case(case: Dict[str, Any]) -> Dict[str, Any]:
    request = ExternalAgentSimulateRequest(
        platform=case["platform"],
        scenario=case["scenario"],
        user=case.get("user", "user"),
        execute=False,
    )

    response = simulate_external_agent_call(request)
    response_dict = response.model_dump()

    actual_decision = _safe_get(
        response_dict,
        "proxy_result",
        "decision",
        default="unknown",
    )

    scope_decision = _safe_get(
        response_dict,
        "proxy_result",
        "agent_auth_profile",
        "scope_decision",
        default="unknown",
    )

    missing_scopes = _safe_get(
        response_dict,
        "proxy_result",
        "agent_auth_profile",
        "missing_scopes",
        default=[],
    )

    sandbox_profile = _safe_get(
        response_dict,
        "proxy_result",
        "sandbox_profile",
        default="-",
    )

    passed = actual_decision == case["expected_decision"]

    return {
        "case_id": case["case_id"],
        "name": case["name"],
        "platform": case["platform"],
        "scenario": case["scenario"],
        "expected_decision": case["expected_decision"],
        "actual_decision": actual_decision,
        "passed": passed,
        "scope_decision": scope_decision,
        "missing_scopes": missing_scopes,
        "sandbox_profile": sandbox_profile,
        "adapter_trace": response_dict.get("adapter_trace", []),
        "normalized_tool": _safe_get(
            response_dict,
            "normalized_tool_request",
            "tool",
            default="-",
        ),
        "normalized_params": _safe_get(
            response_dict,
            "normalized_tool_request",
            "params",
            default={},
        ),
        "reason": _safe_get(
            response_dict,
            "proxy_result",
            "reason",
            default=[],
        ),
    }


def main() -> None:
    cases: List[Dict[str, Any]] = [
        {
            "case_id": "adapter_eval_001",
            "name": "OpenClaw valid public read",
            "platform": "openclaw",
            "scenario": "valid_public_read",
            "user": "user",
            "expected_decision": "allow",
        },
        {
            "case_id": "adapter_eval_002",
            "name": "WorkBuddy insufficient scope external email",
            "platform": "workbuddy",
            "scenario": "insufficient_scope_email",
            "user": "user",
            "expected_decision": "deny",
        },
        {
            "case_id": "adapter_eval_003",
            "name": "WorkBuddy valid internal email requires confirmation",
            "platform": "workbuddy",
            "scenario": "valid_internal_email_confirm",
            "user": "user",
            "expected_decision": "confirm",
        },
        {
            "case_id": "adapter_eval_004",
            "name": "Custom Agent shell blocked by sandbox profile",
            "platform": "custom",
            "scenario": "sandbox_block_shell",
            "user": "admin",
            "expected_decision": "deny",
        },
    ]

    case_results = [_run_case(case) for case in cases]
    passed_cases = sum(1 for item in case_results if item["passed"])
    total_cases = len(case_results)

    result_path = _next_result_path()

    result = {
        "result_id": result_path.stem,
        "module": "external_agent_adapter_eval",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "description": (
            "Repeatable evaluation for OpenClaw / WorkBuddy / Custom Agent "
            "adapter simulation through Tool Proxy, OAuth-style scope, "
            "Capability Contract, Runtime Monitor, and sandbox profile."
        ),
        "cases": case_results,
        "summary": {
            "total_cases": total_cases,
            "passed_cases": passed_cases,
            "accuracy": round(passed_cases / total_cases, 4) if total_cases else 0,
            "all_passed": passed_cases == total_cases,
            "conclusion": (
                "External Agent Adapter evaluation verifies that valid public read is allowed, "
                "insufficient external email is denied, valid internal email requires confirmation, "
                "and shell execution is blocked by sandbox policy."
            ),
        },
    }

    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 72)
    print("External Agent Adapter Evaluation")
    print("=" * 72)

    for item in case_results:
        status = "PASS" if item["passed"] else "FAIL"
        print(
            f"[{status}] {item['case_id']} | "
            f"{item['name']} | expected={item['expected_decision']} | "
            f"actual={item['actual_decision']} | scope={item['scope_decision']}"
        )

    print("-" * 72)
    print(f"Passed: {passed_cases} / {total_cases}")
    print(f"Accuracy: {result['summary']['accuracy']}")
    print(f"Saved to: {result_path}")

    if passed_cases != total_cases:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
