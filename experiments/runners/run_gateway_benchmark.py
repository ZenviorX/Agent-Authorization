import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT_DIR = Path(__file__).resolve().parents[1]

# 保证无论从哪里运行脚本，都能正确导入 backend 包
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from backend.schemas import ToolCallRequest
from backend.gateway.gateway import check_tool_call


CASE_FILE = ROOT_DIR / "security_cases" / "gateway_cases.json"
RESULT_FILE = ROOT_DIR / "experiments" / "gateway_benchmark_results.csv"
REPORT_FILE = ROOT_DIR / "experiments" / "gateway_benchmark_report.md"


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


def write_markdown_report(
    rows: List[Dict[str, Any]],
    total: int,
    passed: int,
    normal_total: int,
    normal_passed: int,
    attack_total: int,
    attack_passed: int,
) -> None:
    accuracy = passed / total if total else 0
    normal_rate = normal_passed / normal_total if normal_total else 0
    attack_rate = attack_passed / attack_total if attack_total else 0

    lines = []
    lines.append("# Agent Authorization Gateway Benchmark Report")
    lines.append("")
    lines.append("## 1. Benchmark Overview")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Total cases | {total} |")
    lines.append(f"| Passed cases | {passed} |")
    lines.append(f"| Overall accuracy | {accuracy:.2%} |")
    lines.append(f"| Normal task pass consistency | {normal_rate:.2%} |")
    lines.append(f"| Attack blocking consistency | {attack_rate:.2%} |")
    lines.append("")
    lines.append("## 2. Case Results")
    lines.append("")
    lines.append("| ID | Category | Expected | Actual | Risk Score | Risk Level | Passed |")
    lines.append("|---|---|---|---|---:|---|---|")

    for row in rows:
        passed_text = "Yes" if row["passed"] else "No"
        lines.append(
            f"| {row['id']} | {row['category']} | {row['expected']} | "
            f"{row['actual']} | {row['risk_score']} | {row['risk_level']} | {passed_text} |"
        )

    failed_rows = [row for row in rows if not row["passed"]]

    lines.append("")
    lines.append("## 3. Failed Cases")
    lines.append("")

    if not failed_rows:
        lines.append("No failed cases were found in this benchmark run.")
    else:
        for row in failed_rows:
            lines.append(
                f"- `{row['id']}`: expected `{row['expected']}`, "
                f"actual `{row['actual']}`, risk score `{row['risk_score']}`."
            )

    lines.append("")
    lines.append("## 4. Interpretation")
    lines.append("")
    lines.append(
        "This benchmark evaluates whether the authorization gateway can correctly "
        "handle normal tool calls and block or escalate risky Agent tool calls. "
        "The cases cover public file access, course file access, secret file access, "
        "path traversal, absolute path access, prompt injection content, high-risk shell commands, "
        "unknown tools, and sensitive information exfiltration through email."
    )
    lines.append("")
    lines.append(
        "The result can be used as quantitative evidence for the effectiveness of "
        "the gateway's risk scoring, role-based authorization, path protection, "
        "prompt injection detection, and explainable decision mechanism."
    )
    lines.append("")

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    cases: List[Dict[str, Any]] = json.loads(CASE_FILE.read_text(encoding="utf-8-sig"))

    rows = []
    total = len(cases)
    passed = 0

    normal_total = 0
    normal_passed = 0
    attack_total = 0
    attack_passed = 0

    for case in cases:
        request = ToolCallRequest(**case["request"])
        result = check_tool_call(request)

        decision = result["decision"]
        ok = is_expected(case, decision)

        if ok:
            passed += 1

        if case["category"] == "normal":
            normal_total += 1
            if ok:
                normal_passed += 1

        if case["category"] == "attack":
            attack_total += 1
            if ok:
                attack_passed += 1

        rows.append({
            "id": case["id"],
            "category": case["category"],
            "description": case["description"],
            "expected": format_expected(case),
            "actual": decision,
            "risk_score": result.get("risk_score"),
            "risk_level": result.get("risk_level"),
            "passed": ok,
            "reason": " | ".join(result.get("reason", [])),
        })

    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with RESULT_FILE.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "category",
                "description",
                "expected",
                "actual",
                "risk_score",
                "risk_level",
                "passed",
                "reason",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    write_markdown_report(
        rows=rows,
        total=total,
        passed=passed,
        normal_total=normal_total,
        normal_passed=normal_passed,
        attack_total=attack_total,
        attack_passed=attack_passed,
    )

    accuracy = passed / total if total else 0
    normal_rate = normal_passed / normal_total if normal_total else 0
    attack_rate = attack_passed / attack_total if attack_total else 0

    print("========== Agent Authorization Gateway Benchmark ==========")
    print(f"Total cases: {total}")
    print(f"Passed cases: {passed}")
    print(f"Overall accuracy: {accuracy:.2%}")
    print(f"Normal task pass consistency: {normal_rate:.2%}")
    print(f"Attack blocking consistency: {attack_rate:.2%}")
    print(f"CSV result file: {RESULT_FILE}")
    print(f"Markdown report file: {REPORT_FILE}")

    print("\nFailed cases:")
    failed_rows = [row for row in rows if not row["passed"]]
    if not failed_rows:
        print("None")
    else:
        for row in failed_rows:
            print(
                f"- {row['id']}: expected={row['expected']}, "
                f"actual={row['actual']}, risk={row['risk_score']}"
            )


if __name__ == "__main__":
    main()
