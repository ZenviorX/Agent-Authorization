from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, List

from backend.agents.offline_runtime_agent import OfflineRuntimeAgent
from backend.evidence.integrity import attach_integrity_manifest
from backend.task_session.session_executor import execute_task_session


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_PATH = PROJECT_ROOT / "security_cases" / "llm_runtime_cases.json"
DEFAULT_RESULT_JSON = None
DEFAULT_RESULT_HTML = None



def _next_result_paths(results_dir: Path | None = None) -> tuple[Path, Path]:
    """
    ? Results/Result_XXX.json ? Results/Result_XXX.html ??????????????
    ???? Result_025.json/html??????? Result_026.json/html?
    """
    results_dir = results_dir or (PROJECT_ROOT / "Results")
    results_dir.mkdir(parents=True, exist_ok=True)

    max_index = 0

    for file_path in list(results_dir.glob("Result_*.json")) + list(results_dir.glob("Result_*.html")):
        stem = file_path.stem

        try:
            number_text = stem.split("_", 1)[1]
            number = int(number_text)
        except (IndexError, ValueError):
            continue

        max_index = max(max_index, number)

    next_index = max_index + 1

    return (
        results_dir / f"Result_{next_index:03d}.json",
        results_dir / f"Result_{next_index:03d}.html",
    )


def _load_cases(case_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(case_path.read_text(encoding="utf-8-sig"))

    if not isinstance(data, list):
        raise ValueError(f"{case_path} top-level value must be a list")

    return data


def _model_dump(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()

    if hasattr(model, "dict"):
        return model.dict()

    if isinstance(model, dict):
        return model

    return {"value": str(model)}


def _final_decision_matches(expected: Dict[str, Any], actual: str) -> tuple[bool, str]:
    if "final_decision" in expected:
        wanted = str(expected["final_decision"])
        return actual == wanted, f"expected final_decision={wanted}, actual={actual}"

    if "final_decision_in" in expected:
        allowed = {str(item) for item in expected["final_decision_in"]}
        return actual in allowed, f"expected final_decision in {sorted(allowed)}, actual={actual}"

    return True, "no final decision expectation"


def _planned_tool_matches(expected: Dict[str, Any], planned_tools: List[str]) -> tuple[bool, str]:
    expected_tools = set(str(item) for item in expected.get("expected_planned_tool_in", []))

    if expected.get("first_tool"):
        expected_tools.add(str(expected["first_tool"]))

    if expected.get("expected_later_tool"):
        expected_tools.add(str(expected["expected_later_tool"]))

    if not expected_tools:
        return True, "no planned tool expectation"

    actual_tools = set(planned_tools)
    ok = bool(expected_tools & actual_tools)
    return ok, f"expected any planned tool in {sorted(expected_tools)}, actual={planned_tools}"


def _recipient_safety_matches(expected: Dict[str, Any], executed_emails: List[Dict[str, Any]]) -> tuple[bool, str]:
    forbidden = {str(item) for item in expected.get("must_not_send_to", [])}

    if not forbidden:
        return True, "no forbidden recipient expectation"

    actual_recipients = {
        str(item.get("to"))
        for item in executed_emails
        if item.get("executed") is True
    }

    leaked = sorted(forbidden & actual_recipients)
    ok = not leaked

    return ok, f"forbidden recipients={sorted(forbidden)}, executed_recipients={sorted(actual_recipients)}"


def _execution_safety_matches(expected: Dict[str, Any], steps: List[Dict[str, Any]]) -> tuple[bool, str]:
    if expected.get("must_not_execute") is not True:
        return True, "no must_not_execute expectation"

    executed_steps = [
        {
            "step_id": step.get("step_id"),
            "tool": step.get("tool"),
            "params": step.get("real_params") or step.get("params"),
        }
        for step in steps
        if step.get("executed") is True
    ]

    ok = not executed_steps

    return ok, f"executed_steps={executed_steps}"


def _label_expectation_matches(expected: Dict[str, Any], steps: List[Dict[str, Any]]) -> tuple[bool, str]:
    required = set(str(item) for item in expected.get("expected_output_labels_after_first_step", []))

    if not required:
        return True, "no output label expectation"

    if not steps:
        return False, "no steps were planned"

    first_labels = set(str(item) for item in steps[0].get("output_labels", []))
    ok = required <= first_labels

    return ok, f"expected first step labels include {sorted(required)}, actual={sorted(first_labels)}"


def _evaluate_case(case: Dict[str, Any], session_data: Dict[str, Any]) -> Dict[str, Any]:
    expected = dict(case.get("expected", {}))
    steps = list(session_data.get("steps", []))

    planned_tools = [str(step.get("tool")) for step in steps]

    executed_emails = [
        {
            "to": (step.get("real_params") or step.get("params") or {}).get("to"),
            "executed": step.get("executed"),
        }
        for step in steps
        if step.get("tool") == "email.send"
    ]

    checks = []

    for name, result in [
        ("final_decision", _final_decision_matches(expected, str(session_data.get("final_decision")))),
        ("planned_tool", _planned_tool_matches(expected, planned_tools)),
        ("recipient_safety", _recipient_safety_matches(expected, executed_emails)),
        ("execution_safety", _execution_safety_matches(expected, steps)),
        ("label_expectation", _label_expectation_matches(expected, steps)),
    ]:
        ok, detail = result
        checks.append(
            {
                "name": name,
                "passed": ok,
                "detail": detail,
            }
        )

    passed = all(item["passed"] for item in checks)

    return {
        "passed": passed,
        "checks": checks,
    }


def run_benchmark(
    *,
    case_path: Path = DEFAULT_CASE_PATH,
    write_reports: bool = True,
    result_json: Path | None = DEFAULT_RESULT_JSON,
    result_html: Path | None = DEFAULT_RESULT_HTML,
) -> Dict[str, Any]:
    cases = _load_cases(case_path)
    agent = OfflineRuntimeAgent()

    case_results: List[Dict[str, Any]] = []

    for case in cases:
        session = agent.plan_case(case)
        executed_session = execute_task_session(session)
        session_data = _model_dump(executed_session)

        evaluation = _evaluate_case(case, session_data)

        case_results.append(
            {
                "id": case.get("id"),
                "category": case.get("category"),
                "description": case.get("description"),
                "passed": evaluation["passed"],
                "final_decision": session_data.get("final_decision"),
                "status": session_data.get("status"),
                "step_count": len(session_data.get("steps", [])),
                "checks": evaluation["checks"],
                "steps": [
                    {
                        "step_id": step.get("step_id"),
                        "tool": step.get("tool"),
                        "params": step.get("params"),
                        "real_params": step.get("real_params"),
                        "decision": step.get("decision"),
                        "risk_score": step.get("risk_score"),
                        "executed": step.get("executed"),
                        "blocked": step.get("blocked"),
                        "requires_confirmation": step.get("requires_confirmation"),
                        "input_labels": step.get("input_labels"),
                        "output_labels": step.get("output_labels"),
                        "reason": step.get("reason"),
                    }
                    for step in session_data.get("steps", [])
                ],
            }
        )

    total = len(case_results)
    passed = sum(1 for item in case_results if item["passed"])
    failed = total - passed

    by_category = Counter(str(item.get("category")) for item in case_results)
    passed_by_category = Counter(
        str(item.get("category"))
        for item in case_results
        if item["passed"]
    )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_file": str(case_path.relative_to(PROJECT_ROOT)),
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "by_category": dict(by_category),
        "passed_by_category": dict(passed_by_category),
    }

    if write_reports:
        if result_json is None or result_html is None:
            result_json, result_html = _next_result_paths()

        summary["json_report"] = str(result_json)
        summary["html_report"] = str(result_html)

    report = {
        "summary": summary,
        "cases": case_results,
    }

    report = attach_integrity_manifest(report)

    if write_reports:
        if result_json is None or result_html is None:
            result_json, result_html = _next_result_paths()

        result_json.parent.mkdir(parents=True, exist_ok=True)
        result_html.parent.mkdir(parents=True, exist_ok=True)

        result_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        result_html.write_text(
            _render_html_report(report),
            encoding="utf-8",
        )


    return report


def _render_html_report(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    rows = []

    for item in report["cases"]:
        badge = "PASS" if item["passed"] else "FAIL"
        checks = "<br>".join(
            f"{'✅' if check['passed'] else '❌'} {escape(check['name'])}: {escape(check['detail'])}"
            for check in item["checks"]
        )

        steps = "<br>".join(
            f"Step {step['step_id']}: {escape(str(step['tool']))} → "
            f"{escape(str(step['decision']))}, risk={escape(str(step['risk_score']))}, "
            f"executed={escape(str(step['executed']))}"
            for step in item["steps"]
        )

        rows.append(
            "<tr>"
            f"<td>{escape(str(item['id']))}</td>"
            f"<td>{escape(str(item['category']))}</td>"
            f"<td><b>{badge}</b></td>"
            f"<td>{escape(str(item['final_decision']))}</td>"
            f"<td>{escape(str(item['status']))}</td>"
            f"<td>{steps}</td>"
            f"<td>{checks}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>LLM Runtime Offline Benchmark</title>
  <style>
    body {{
      font-family: Arial, "Microsoft YaHei", sans-serif;
      margin: 32px;
      color: #172033;
      background: #f6f8fb;
    }}
    .card {{
      background: white;
      border-radius: 14px;
      padding: 20px;
      margin-bottom: 20px;
      box-shadow: 0 4px 16px rgba(20, 30, 50, 0.08);
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      background: white;
      font-size: 14px;
    }}
    th, td {{
      border: 1px solid #e5e8ef;
      padding: 10px;
      vertical-align: top;
    }}
    th {{
      background: #eef3ff;
      text-align: left;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>LLM Runtime Offline Benchmark</h1>
    <p>Generated at: {escape(str(summary["generated_at"]))}</p>
    <p>
      Total: <b>{summary["total"]}</b>,
      Passed: <b>{summary["passed"]}</b>,
      Failed: <b>{summary["failed"]}</b>,
      Pass rate: <b>{summary["pass_rate"]}</b>
    </p>
    <p>By category: {escape(json.dumps(summary["by_category"], ensure_ascii=False))}</p>
  </div>

  <div class="card">
    <h2>Case Results</h2>
    <table>
      <thead>
        <tr>
          <th>Case ID</th>
          <th>Category</th>
          <th>Result</th>
          <th>Final Decision</th>
          <th>Status</th>
          <th>Steps</th>
          <th>Checks</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </div>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run offline benchmark for LLM runtime security cases."
    )
    parser.add_argument(
        "--case-path",
        default=str(DEFAULT_CASE_PATH),
        help="Path to llm_runtime_cases.json",
    )
    parser.add_argument(
        "--json",
        default=None,
        help="Output JSON report path. If omitted, use Results/Result_XXX.json.",
    )
    parser.add_argument(
        "--html",
        default=None,
        help="Output HTML report path. If omitted, use Results/Result_XXX.html.",
    )

    args = parser.parse_args()

    report = run_benchmark(
        case_path=Path(args.case_path),
        result_json=Path(args.json) if args.json else None,
        result_html=Path(args.html) if args.html else None,
        write_reports=True,
    )

    summary = report["summary"]

    print("LLM Runtime Offline Benchmark completed.")
    print(f"Total: {summary['total']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Pass rate: {summary['pass_rate']}")
    print(f"JSON report: {summary.get('json_report')}")
    print(f"HTML report: {summary.get('html_report')}")


if __name__ == "__main__":
    main()
