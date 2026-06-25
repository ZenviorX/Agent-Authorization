"""
Runtime 多步流程评测模块。

该模块用于评测 AgentGuard 在多步骤 Agent 任务中的运行时安全能力：
1. Capability Contract 任务边界约束；
2. input_from_steps 跨步骤标签继承；
3. data_lineage_edges 数据流溯源；
4. Runtime Security Graph 高风险流识别；
5. 阻断后不继续追加步骤。

这不是单步 Gateway case，而是更接近真实 Agent 工具调用链的流程评测。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.capability.capability_contract import CapabilityContract
from backend.runtime.runtime_monitor import (
    build_runtime_security_graph,
    create_runtime_state,
    run_runtime_step,
)


CASE_PATH = PROJECT_ROOT / "security_cases" / "runtime_flow_cases.json"


def load_runtime_flow_cases(path: Path = CASE_PATH) -> List[Dict[str, Any]]:
    if not path.exists():
        raise RuntimeError(f"Runtime flow case file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8-sig"))

    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list.")

    return data


def _expected_match(case: Dict[str, Any], actual: str, key: str) -> bool:
    exact_key = key
    in_key = f"{key}_in"

    if exact_key in case:
        return actual == case[exact_key]

    if in_key in case:
        return actual in case[in_key]

    return True


def _number_expectation_match(
    case: Dict[str, Any],
    actual: int,
    exact_key: str,
    min_key: str,
) -> bool:
    if exact_key in case:
        return actual == int(case[exact_key])

    if min_key in case:
        return actual >= int(case[min_key])

    return True


def run_runtime_flow_case(case: Dict[str, Any]) -> Dict[str, Any]:
    contract = CapabilityContract(**case["contract"])
    state = create_runtime_state(contract)

    started = time.perf_counter()
    step_results: List[Dict[str, Any]] = []

    for index, step in enumerate(case.get("steps", []), start=1):
        before_count = len(state.steps)

        result = run_runtime_step(
            state=state,
            tool=step["tool"],
            params=step.get("params", {}),
            input_labels=step.get("input_labels", []),
            output_content=step.get("output_content"),
            input_from_steps=step.get("input_from_steps", []),
        )

        after_count = len(state.steps)

        step_results.append(
            {
                "index": index,
                "tool": step["tool"],
                "decision": result.decision,
                "risk_score": result.risk_score,
                "reason": result.reason,
                "recorded": after_count > before_count,
            }
        )

        if state.is_blocked:
            # Runtime 已阻断后，不再模拟后续工具调用。
            # 这更符合真实 Agent 安全运行时的 fail-closed 行为。
            break

    elapsed_ms = (time.perf_counter() - started) * 1000

    graph = build_runtime_security_graph(state)

    executed_step_count = sum(1 for step in state.steps if step.executed)
    recorded_step_count = len(state.steps)
    high_risk_flow_count = graph["summary"]["high_risk_flow_count"]

    checks = []

    final_decision_ok = _expected_match(
        case,
        state.final_decision,
        "expected_final_decision",
    )

    checks.append(
        {
            "name": "final_decision",
            "passed": final_decision_ok,
            "actual": state.final_decision,
            "expected": case.get(
                "expected_final_decision",
                case.get("expected_final_decision_in", "any"),
            ),
        }
    )

    blocked_expected = case.get("expected_blocked")
    blocked_expected_in = case.get("expected_blocked_in")

    if blocked_expected is not None:
        blocked_ok = state.is_blocked is bool(blocked_expected)
    elif blocked_expected_in is not None:
        blocked_ok = state.is_blocked in blocked_expected_in
    else:
        blocked_ok = True

    checks.append(
        {
            "name": "blocked",
            "passed": blocked_ok,
            "actual": state.is_blocked,
            "expected": (
                blocked_expected
                if blocked_expected is not None
                else blocked_expected_in
                if blocked_expected_in is not None
                else "any"
            ),
        }
    )

    high_risk_ok = _number_expectation_match(
        case,
        high_risk_flow_count,
        "expected_high_risk_flow_count",
        "expected_high_risk_flow_count_min",
    )

    checks.append(
        {
            "name": "high_risk_flow_count",
            "passed": high_risk_ok,
            "actual": high_risk_flow_count,
            "expected": case.get(
                "expected_high_risk_flow_count",
                f">= {case.get('expected_high_risk_flow_count_min')}"
                if "expected_high_risk_flow_count_min" in case
                else "any",
            ),
        }
    )

    if "expected_executed_step_count" in case:
        checks.append(
            {
                "name": "executed_step_count",
                "passed": executed_step_count == int(case["expected_executed_step_count"]),
                "actual": executed_step_count,
                "expected": int(case["expected_executed_step_count"]),
            }
        )

    if "expected_recorded_step_count" in case:
        checks.append(
            {
                "name": "recorded_step_count",
                "passed": recorded_step_count == int(case["expected_recorded_step_count"]),
                "actual": recorded_step_count,
                "expected": int(case["expected_recorded_step_count"]),
            }
        )

    expected_risky_labels = set(case.get("expected_risky_labels", []))

    if expected_risky_labels:
        actual_risky_labels = set()

        for flow in graph.get("high_risk_flows", []):
            actual_risky_labels.update(flow.get("risky_labels", []))

        checks.append(
            {
                "name": "expected_risky_labels",
                "passed": expected_risky_labels.issubset(actual_risky_labels),
                "actual": sorted(actual_risky_labels),
                "expected": sorted(expected_risky_labels),
            }
        )

    passed = all(item["passed"] for item in checks)

    return {
        "id": case.get("id"),
        "category": case.get("category", "unknown"),
        "description": case.get("description", ""),
        "passed": passed,
        "checks": checks,
        "elapsed_ms": round(elapsed_ms, 4),
        "step_results": step_results,
        "state": state.model_dump(),
        "security_graph": graph,
        "summary": {
            "final_decision": state.final_decision,
            "is_blocked": state.is_blocked,
            "used_risk": state.used_risk,
            "recorded_step_count": recorded_step_count,
            "executed_step_count": executed_step_count,
            "high_risk_flow_count": high_risk_flow_count,
            "graph_risk_level": graph.get("graph_risk_level"),
        },
    }


def evaluate_runtime_flows(
    cases: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    cases = cases if cases is not None else load_runtime_flow_cases()

    rows = []
    started = time.perf_counter()

    for case in cases:
        rows.append(run_runtime_flow_case(case))

    elapsed_ms = (time.perf_counter() - started) * 1000

    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    attack_total = sum(1 for row in rows if row["category"] == "attack")
    normal_total = sum(1 for row in rows if row["category"] == "normal")
    high_risk_flow_total = sum(
        row["summary"]["high_risk_flow_count"]
        for row in rows
    )
    blocked_total = sum(1 for row in rows if row["summary"]["is_blocked"])

    return {
        "summary": {
            "total_cases": total,
            "passed_cases": passed,
            "failed_cases": total - passed,
            "accuracy": passed / total if total else 0.0,
            "attack_total": attack_total,
            "normal_total": normal_total,
            "blocked_total": blocked_total,
            "high_risk_flow_total": high_risk_flow_total,
            "elapsed_ms": round(elapsed_ms, 4),
        },
        "rows": rows,
    }


def main() -> None:
    report = evaluate_runtime_flows()
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))

    failed = [
        row
        for row in report["rows"]
        if not row["passed"]
    ]

    if failed:
        print("")
        print("Failed runtime flow cases:")
        print(json.dumps(failed, ensure_ascii=False, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
