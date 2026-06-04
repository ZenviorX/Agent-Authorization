import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.gateway.gateway import check_tool_call
from backend.schemas import ToolCallRequest
from experiments.runners.baseline_deciders import allow_all_decider, keyword_decider


CASE_DIR = PROJECT_ROOT / "security_cases"
OUT_CSV = PROJECT_ROOT / "experiments" / "outputs" / "baseline_comparison_results.csv"
OUT_JSON = PROJECT_ROOT / "experiments" / "outputs" / "baseline_comparison_summary.json"
OUT_MD = PROJECT_ROOT / "experiments" / "reports" / "baseline_comparison_report.md"

StrategyFunc = Callable[[Dict[str, Any]], Dict[str, Any]]


def load_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for path in sorted(CASE_DIR.glob("gateway_cases*.json")):
        with open(path, "r", encoding="utf-8-sig") as f:
            loaded = json.load(f)
        if not isinstance(loaded, list):
            raise ValueError(f"{path} 顶层必须是列表")
        for item in loaded:
            item["_source_file"] = path.name
            cases.append(item)
    if not cases:
        raise RuntimeError("没有找到 gateway_cases*.json，请检查 security_cases 目录。")
    return cases


def expected_match(case: Dict[str, Any], decision: str) -> bool:
    if "expected_decision" in case:
        return decision == case["expected_decision"]
    if "expected_decision_in" in case:
        return decision in case["expected_decision_in"]
    raise ValueError(f"case {case.get('id')} 缺少 expected_decision 或 expected_decision_in")


def normalize_security_label(case: Dict[str, Any]) -> str:
    category = str(case.get("category", "")).lower()
    if category in {"normal", "benign", "safe"}:
        return "normal"
    if category in {"attack", "malicious", "dangerous"}:
        return "attack"
    return "suspicious"


def normalize_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def gateway_decider(request_data: Dict[str, Any]) -> Dict[str, Any]:
    request = ToolCallRequest(**request_data)
    return check_tool_call(request)


def evaluate_strategy(strategy_name: str, decider: StrategyFunc, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    total_latency = 0.0
    passed = 0
    decision_counter = Counter()
    category_counter = Counter()
    category_total = defaultdict(int)
    category_passed = defaultdict(int)
    attack_total = 0
    attack_blocked_or_confirmed = 0
    attack_unsafe_allowed = 0
    normal_total = 0
    normal_denied = 0
    suspicious_total = 0
    suspicious_confirm_or_deny = 0
    failures = []

    for case in cases:
        start = time.perf_counter()
        result = decider(case["request"])
        latency_ms = (time.perf_counter() - start) * 1000
        total_latency += latency_ms

        decision = result.get("decision")
        risk_score = result.get("risk_score")
        risk_level = result.get("risk_level", "")
        reasons = normalize_list(result.get("reason", []))
        ok = expected_match(case, decision)
        category = case.get("category", "unknown")
        security_label = normalize_security_label(case)

        if ok:
            passed += 1
        else:
            failures.append({
                "id": case.get("id"),
                "source_file": case.get("_source_file", "unknown"),
                "category": category,
                "description": case.get("description", ""),
                "expected": case.get("expected_decision", case.get("expected_decision_in")),
                "actual": decision,
                "risk_score": risk_score,
                "reason": reasons,
            })

        decision_counter[decision] += 1
        category_counter[category] += 1
        category_total[category] += 1
        if ok:
            category_passed[category] += 1

        if security_label == "attack":
            attack_total += 1
            if decision in {"deny", "confirm"}:
                attack_blocked_or_confirmed += 1
            if decision == "allow":
                attack_unsafe_allowed += 1
        elif security_label == "normal":
            normal_total += 1
            if decision == "deny":
                normal_denied += 1
        else:
            suspicious_total += 1
            if decision in {"confirm", "deny"}:
                suspicious_confirm_or_deny += 1

        rows.append({
            "strategy": strategy_name,
            "id": case.get("id"),
            "source_file": case.get("_source_file", "unknown"),
            "category": category,
            "security_label": security_label,
            "description": case.get("description", ""),
            "expected": case.get("expected_decision", case.get("expected_decision_in")),
            "actual": decision,
            "passed": ok,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "latency_ms": round(latency_ms, 3),
            "reason": " | ".join(reasons),
        })

    total = len(cases)
    category_accuracy = {
        category: {
            "total": total_count,
            "passed": category_passed[category],
            "accuracy": category_passed[category] / total_count if total_count else 0.0,
        }
        for category, total_count in category_total.items()
    }

    return {
        "strategy": strategy_name,
        "rows": rows,
        "summary": {
            "total_cases": total,
            "passed_cases": passed,
            "accuracy": passed / total if total else 0.0,
            "avg_latency_ms": total_latency / total if total else 0.0,
            "decision_distribution": dict(decision_counter),
            "category_distribution": dict(category_counter),
            "category_accuracy": category_accuracy,
            "attack_total": attack_total,
            "attack_block_or_confirm_rate": attack_blocked_or_confirmed / attack_total if attack_total else 0.0,
            "attack_unsafe_allow_rate": attack_unsafe_allowed / attack_total if attack_total else 0.0,
            "normal_total": normal_total,
            "normal_false_deny_rate": normal_denied / normal_total if normal_total else 0.0,
            "suspicious_total": suspicious_total,
            "suspicious_confirm_or_deny_rate": suspicious_confirm_or_deny / suspicious_total if suspicious_total else 0.0,
            "failed_cases": failures,
        },
    }


def percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def write_outputs(results: List[Dict[str, Any]]) -> None:
    all_rows = []
    summary = {}
    for result in results:
        all_rows.extend(result["rows"])
        summary[result["strategy"]] = result["summary"]

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()) if all_rows else [])
        writer.writeheader()
        writer.writerows(all_rows)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    md = [
        "# Agent Authorization Gateway 对比实验报告\n\n",
        "## 1. 总体对比结果\n\n",
        "| 方案 | 总样例数 | 总体一致率 | 攻击阻断/确认率 | 攻击误放行率 | 正常误拒绝率 | 平均延迟 |\n",
        "|---|---:|---:|---:|---:|---:|---:|\n",
    ]
    for strategy, item in summary.items():
        md.append(
            f"| {strategy} | {item['total_cases']} | {percent(item['accuracy'])} | "
            f"{percent(item['attack_block_or_confirm_rate'])} | "
            f"{percent(item['attack_unsafe_allow_rate'])} | "
            f"{percent(item['normal_false_deny_rate'])} | {item['avg_latency_ms']:.3f} ms |\n"
        )

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("".join(md))


def main() -> None:
    cases = load_cases()
    strategies = [
        ("allow_all", allow_all_decider),
        ("keyword", keyword_decider),
        ("gateway", gateway_decider),
    ]
    results = []
    for strategy_name, decider in strategies:
        print(f"Running strategy: {strategy_name}")
        result = evaluate_strategy(strategy_name, decider, cases)
        results.append(result)
        item = result["summary"]
        print(
            f"  accuracy={percent(item['accuracy'])}, "
            f"attack_block_or_confirm={percent(item['attack_block_or_confirm_rate'])}, "
            f"attack_unsafe_allow={percent(item['attack_unsafe_allow_rate'])}, "
            f"normal_false_deny={percent(item['normal_false_deny_rate'])}, "
            f"avg_latency={item['avg_latency_ms']:.3f} ms"
        )
    write_outputs(results)
    print("========== Baseline Comparison Finished ==========")
    print(f"CSV: {OUT_CSV}")
    print(f"JSON: {OUT_JSON}")
    print(f"Markdown: {OUT_MD}")


if __name__ == "__main__":
    main()
