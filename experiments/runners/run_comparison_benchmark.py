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


CASE_DIR = PROJECT_ROOT / "security_cases"
OUT_CSV = PROJECT_ROOT / "experiments" / "outputs" / "comparison_benchmark_results.csv"
OUT_MD = PROJECT_ROOT / "experiments" / "reports" / "comparison_benchmark_report.md"


def load_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for path in sorted(CASE_DIR.glob("gateway_cases*.json")):
        with open(path, "r", encoding="utf-8-sig") as f:
            loaded = json.load(f)
        if isinstance(loaded, list):
            for item in loaded:
                item["_source_file"] = path.name
                cases.append(item)
    if not cases:
        raise RuntimeError("没有找到 gateway_cases*.json，请检查 security_cases 目录。")
    return cases


def is_safe_for_case(case: Dict[str, Any], decision: str) -> bool:
    category = str(case.get("category", "")).lower()
    if category == "normal":
        return decision in {"allow", "confirm"}
    return decision in {"confirm", "deny"}


def run_baseline(case: Dict[str, Any]) -> Dict[str, Any]:
    return {"decision": "allow", "risk": 0}


def run_gateway(case: Dict[str, Any]) -> Dict[str, Any]:
    request = ToolCallRequest(**case["request"])
    result = check_tool_call(request)
    return {
        "decision": result.get("decision", "deny"),
        "risk": int(result.get("risk_score", 0) or 0),
    }


def rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def write_report(rows: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    lines = [
        "# Security Comparison Benchmark Report\n\n",
        "## 1. Summary Metrics\n\n",
        "| Metric | Baseline | Gateway |\n",
        "|---|---:|---:|\n",
        f"| Overall safe decision rate | {summary['baseline_safe_rate']:.2%} | {summary['gateway_safe_rate']:.2%} |\n",
        f"| Normal workflow acceptance | {summary['baseline_normal_acceptance']:.2%} | {summary['gateway_normal_acceptance']:.2%} |\n",
        f"| Risk workflow protection | {summary['baseline_risk_protection']:.2%} | {summary['gateway_risk_protection']:.2%} |\n",
        "\n## 2. Case-level Results\n\n",
        "| ID | Category | Baseline | Gateway | Gateway Risk |\n",
        "|---|---|---|---|---:|\n",
    ]

    for row in rows:
        lines.append(
            f"| {row['id']} | {row['category']} | {row['baseline_decision']} | "
            f"{row['gateway_decision']} | {row['gateway_risk']} |\n"
        )

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(lines), encoding="utf-8")


def main() -> None:
    cases = load_cases()
    rows = []
    normal_cases = [case for case in cases if str(case.get("category", "")).lower() == "normal"]
    risk_cases = [case for case in cases if case not in normal_cases]

    counters = {
        "baseline_safe": 0,
        "gateway_safe": 0,
        "baseline_normal_accept": 0,
        "gateway_normal_accept": 0,
        "baseline_risk_protect": 0,
        "gateway_risk_protect": 0,
    }

    for case in cases:
        baseline = run_baseline(case)
        gateway = run_gateway(case)
        baseline_safe = is_safe_for_case(case, baseline["decision"])
        gateway_safe = is_safe_for_case(case, gateway["decision"])
        category = str(case.get("category", "unknown"))

        counters["baseline_safe"] += int(baseline_safe)
        counters["gateway_safe"] += int(gateway_safe)
        if category.lower() == "normal":
            counters["baseline_normal_accept"] += int(baseline["decision"] in {"allow", "confirm"})
            counters["gateway_normal_accept"] += int(gateway["decision"] in {"allow", "confirm"})
        else:
            counters["baseline_risk_protect"] += int(baseline["decision"] in {"confirm", "deny"})
            counters["gateway_risk_protect"] += int(gateway["decision"] in {"confirm", "deny"})

        rows.append({
            "id": case.get("id"),
            "category": category,
            "description": case.get("description", ""),
            "baseline_decision": baseline["decision"],
            "gateway_decision": gateway["decision"],
            "baseline_safe": baseline_safe,
            "gateway_safe": gateway_safe,
            "gateway_risk": gateway["risk"],
        })

    total = len(cases)
    normal_total = len(normal_cases)
    risk_total = len(risk_cases)
    summary = {
        "baseline_safe_rate": rate(counters["baseline_safe"], total),
        "gateway_safe_rate": rate(counters["gateway_safe"], total),
        "baseline_normal_acceptance": rate(counters["baseline_normal_accept"], normal_total),
        "gateway_normal_acceptance": rate(counters["gateway_normal_accept"], normal_total),
        "baseline_risk_protection": rate(counters["baseline_risk_protect"], risk_total),
        "gateway_risk_protection": rate(counters["gateway_risk_protect"], risk_total),
    }

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    write_report(rows, summary)

    print("========== Security Comparison Benchmark ==========")
    print(f"Total cases: {total}")
    print(f"Baseline safe decision rate: {summary['baseline_safe_rate']:.2%}")
    print(f"Gateway safe decision rate: {summary['gateway_safe_rate']:.2%}")
    print(f"CSV result file: {OUT_CSV}")
    print(f"Markdown report file: {OUT_MD}")


if __name__ == "__main__":
    main()
