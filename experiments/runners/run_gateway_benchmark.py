import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.gateway.gateway import check_tool_call
from backend.schemas import ToolCallRequest


CASE_FILE = PROJECT_ROOT / "security_cases" / "gateway_cases.json"
OUT_CSV = PROJECT_ROOT / "experiments" / "outputs" / "gateway_benchmark_results.csv"
OUT_MD = PROJECT_ROOT / "experiments" / "reports" / "gateway_benchmark_report.md"


def is_expected(case: Dict[str, Any], decision: str) -> bool:
    if "expected_decision" in case:
        return decision == case["expected_decision"]
    if "expected_decision_in" in case:
        return decision in case["expected_decision_in"]
    return False


def format_expected(case: Dict[str, Any]) -> str:
    if "expected_decision" in case:
        return str(case["expected_decision"])
    if "expected_decision_in" in case:
        return " / ".join(case["expected_decision_in"])
    return "unknown"


def write_markdown_report(rows: List[Dict[str, Any]]) -> None:
    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    normal_rows = [row for row in rows if row["category"] == "normal"]
    attack_rows = [row for row in rows if row["category"] == "attack"]

    def rate(part: int, whole: int) -> float:
        return part / whole if whole else 0.0

    md = [
        "# Agent Authorization Gateway Benchmark Report\n\n",
        "## 1. Benchmark Overview\n\n",
        "| Metric | Value |\n",
        "|---|---:|\n",
        f"| Total cases | {total} |\n",
        f"| Passed cases | {passed} |\n",
        f"| Overall accuracy | {rate(passed, total):.2%} |\n",
        f"| Normal task pass consistency | {rate(sum(1 for row in normal_rows if row['passed']), len(normal_rows)):.2%} |\n",
        f"| Attack blocking consistency | {rate(sum(1 for row in attack_rows if row['passed']), len(attack_rows)):.2%} |\n",
        "\n## 2. Case Results\n\n",
        "| ID | Category | Expected | Actual | Risk Score | Risk Level | Passed |\n",
        "|---|---|---|---|---:|---|---|\n",
    ]

    for row in rows:
        passed_text = "Yes" if row["passed"] else "No"
        md.append(
            f"| {row['id']} | {row['category']} | {row['expected']} | "
            f"{row['actual']} | {row['risk_score']} | {row['risk_level']} | {passed_text} |\n"
        )

    failed_rows = [row for row in rows if not row["passed"]]
    md.append("\n## 3. Failed Cases\n\n")
    if not failed_rows:
        md.append("No failed cases were found in this benchmark run.\n")
    else:
        for row in failed_rows:
            md.append(
                f"- `{row['id']}`: expected `{row['expected']}`, "
                f"actual `{row['actual']}`, risk score `{row['risk_score']}`.\n"
            )

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(md), encoding="utf-8")


def main() -> None:
    cases: List[Dict[str, Any]] = json.loads(CASE_FILE.read_text(encoding="utf-8-sig"))
    rows: List[Dict[str, Any]] = []

    for case in cases:
        request = ToolCallRequest(**case["request"])
        result = check_tool_call(request)
        decision = result["decision"]
        ok = is_expected(case, decision)
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "description": case["description"],
                "expected": format_expected(case),
                "actual": decision,
                "risk_score": result.get("risk_score"),
                "risk_level": result.get("risk_level"),
                "passed": ok,
                "reason": " | ".join(result.get("reason", [])),
            }
        )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    write_markdown_report(rows)

    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    accuracy = passed / total if total else 0.0

    print("========== Agent Authorization Gateway Benchmark ==========")
    print(f"Total cases: {total}")
    print(f"Passed cases: {passed}")
    print(f"Overall accuracy: {accuracy:.2%}")
    print(f"CSV result file: {OUT_CSV}")
    print(f"Markdown report file: {OUT_MD}")


if __name__ == "__main__":
    main()
