import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from backend.attack_chain import AttackChainDetector


CASE_FILE = ROOT_DIR / "security_cases" / "attack_chain_cases.json"
RESULT_FILE = ROOT_DIR / "experiments" / "attack_chain_benchmark_results.csv"
REPORT_FILE = ROOT_DIR / "experiments" / "attack_chain_benchmark_report.md"


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


def run_case(case: Dict[str, Any]) -> Dict[str, Any]:
    detector = AttackChainDetector(session_id=case["id"])
    result = None

    for step in case["steps"]:
        result = detector.add_event(
            tool=step["tool"],
            params=step.get("params", {}),
            gateway_result=step.get("gateway_result", {}),
        )

    return result or detector.to_dict()


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
    lines.append("# Attack Chain Benchmark Report")
    lines.append("")
    lines.append("## 1. Benchmark Overview")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Total cases | {total} |")
    lines.append(f"| Passed cases | {passed} |")
    lines.append(f"| Overall accuracy | {accuracy:.2%} |")
    lines.append(f"| Normal chain consistency | {normal_rate:.2%} |")
    lines.append(f"| Attack chain detection consistency | {attack_rate:.2%} |")
    lines.append("")
    lines.append("## 2. Case Results")
    lines.append("")
    lines.append("| ID | Category | Steps | Expected | Actual | Cumulative Risk | Passed |")
    lines.append("|---|---|---:|---|---|---:|---|")

    for row in rows:
        passed_text = "Yes" if row["passed"] else "No"
        lines.append(
            f"| {row['id']} | {row['category']} | {row['steps']} | "
            f"{row['expected']} | {row['actual']} | {row['cumulative_risk']} | {passed_text} |"
        )

    lines.append("")
    lines.append("## 3. Failed Cases")
    lines.append("")

    failed_rows = [row for row in rows if not row["passed"]]
    if not failed_rows:
        lines.append("No failed cases were found in this benchmark run.")
    else:
        for row in failed_rows:
            lines.append(
                f"- `{row['id']}`: expected `{row['expected']}`, "
                f"actual `{row['actual']}`, cumulative risk `{row['cumulative_risk']}`."
            )

    lines.append("")
    lines.append("## 4. Interpretation")
    lines.append("")
    lines.append(
        "This benchmark evaluates whether the attack-chain detector can distinguish "
        "normal multi-step Agent workflows from suspicious or malicious chains. "
        "The cases cover public reading, internal email sending, prompt injection, "
        "secret file access, data exfiltration, browser-originated injection, and high-risk command execution."
    )
    lines.append("")
    lines.append(
        "Compared with a single attack-chain demo, this benchmark provides more reproducible evidence "
        "for the detector's ability to accumulate session-level risk and escalate final decisions."
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
        result = run_case(case)

        final_decision = result["final_decision"]
        ok = is_expected(case, final_decision)

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

        stages = []
        for event in result.get("events", []):
            stages.append(event.get("stage", "unknown"))

        rows.append({
            "id": case["id"],
            "category": case["category"],
            "description": case["description"],
            "steps": len(case["steps"]),
            "expected": format_expected(case),
            "actual": final_decision,
            "cumulative_risk": result.get("cumulative_risk", 0),
            "passed": ok,
            "stages": " | ".join(stages),
            "summary": " | ".join(result.get("summary", [])),
        })

    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with RESULT_FILE.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "category",
                "description",
                "steps",
                "expected",
                "actual",
                "cumulative_risk",
                "passed",
                "stages",
                "summary",
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

    print("========== Attack Chain Benchmark ==========")
    print(f"Total cases: {total}")
    print(f"Passed cases: {passed}")
    print(f"Overall accuracy: {accuracy:.2%}")
    print(f"Normal chain consistency: {normal_rate:.2%}")
    print(f"Attack chain detection consistency: {attack_rate:.2%}")
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
                f"actual={row['actual']}, cumulative_risk={row['cumulative_risk']}"
            )


if __name__ == "__main__":
    main()
