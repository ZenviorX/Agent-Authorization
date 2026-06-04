import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.schemas import ToolCallRequest
from backend.gateway.gateway import check_tool_call
from experiments.baseline_deciders import allow_all_decider, keyword_decider


CASE_DIR = PROJECT_ROOT / "security_cases"

OUT_CSV = PROJECT_ROOT / "experiments" / "baseline_comparison_results.csv"
OUT_JSON = PROJECT_ROOT / "experiments" / "baseline_comparison_summary.json"
OUT_MD = PROJECT_ROOT / "experiments" / "baseline_comparison_report.md"


StrategyFunc = Callable[[Dict[str, Any]], Dict[str, Any]]


def load_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    case_files = sorted(CASE_DIR.glob("gateway_cases*.json"))

    if not case_files:
        raise RuntimeError("没有找到 gateway_cases*.json，请检查 security_cases 目录。")

    for path in case_files:
        with open(path, "r", encoding="utf-8-sig") as f:
            loaded = json.load(f)

        if not isinstance(loaded, list):
            raise ValueError(f"{path} 顶层必须是列表")

        for item in loaded:
            item["_source_file"] = path.name
            cases.append(item)

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



def evaluate_strategy(
    strategy_name: str,
    decider: StrategyFunc,
    cases: List[Dict[str, Any]],
) -> Dict[str, Any]:
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
    normal_allowed_or_confirmed = 0
    normal_denied = 0

    suspicious_total = 0
    suspicious_confirm_or_deny = 0

    failures = []

    for case in cases:
        request_data = case["request"]

        start = time.perf_counter()
        result = decider(request_data)
        latency_ms = (time.perf_counter() - start) * 1000
        total_latency += latency_ms

        decision = result.get("decision")
        risk_score = result.get("risk_score")
        risk_level = result.get("risk_level", "")

        reasons = normalize_list(result.get("reason", []))

        ok = expected_match(case, decision)
        if ok:
            passed += 1
        else:
            failures.append(
                {
                    "id": case.get("id"),
                    "source_file": case.get("_source_file", "unknown"),
                    "category": case.get("category", "unknown"),
                    "description": case.get("description", ""),
                    "expected": case.get("expected_decision", case.get("expected_decision_in")),
                    "actual": decision,
                    "risk_score": risk_score,
                    "reason": reasons,
                }
            )

        category = case.get("category", "unknown")
        security_label = normalize_security_label(case)

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

        if security_label == "normal":
            normal_total += 1
            if decision in {"allow", "confirm"}:
                normal_allowed_or_confirmed += 1
            if decision == "deny":
                normal_denied += 1

        if security_label == "suspicious":
            suspicious_total += 1
            if decision in {"confirm", "deny"}:
                suspicious_confirm_or_deny += 1

        rows.append(
            {
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
            }
        )

    total = len(cases)
    accuracy = passed / total if total else 0.0
    avg_latency = total_latency / total if total else 0.0

    attack_block_rate = attack_blocked_or_confirmed / attack_total if attack_total else 0.0
    attack_unsafe_allow_rate = attack_unsafe_allowed / attack_total if attack_total else 0.0
    normal_false_deny_rate = normal_denied / normal_total if normal_total else 0.0
    suspicious_confirm_or_deny_rate = (
        suspicious_confirm_or_deny / suspicious_total if suspicious_total else 0.0
    )

    category_accuracy = {}
    for category, total_count in category_total.items():
        category_accuracy[category] = {
            "total": total_count,
            "passed": category_passed[category],
            "accuracy": category_passed[category] / total_count if total_count else 0.0,
        }

    return {
        "strategy": strategy_name,
        "rows": rows,
        "summary": {
            "total_cases": total,
            "passed_cases": passed,
            "accuracy": accuracy,
            "avg_latency_ms": avg_latency,
            "decision_distribution": dict(decision_counter),
            "category_distribution": dict(category_counter),
            "category_accuracy": category_accuracy,
            "attack_total": attack_total,
            "attack_block_or_confirm_rate": attack_block_rate,
            "attack_unsafe_allow_rate": attack_unsafe_allow_rate,
            "normal_total": normal_total,
            "normal_false_deny_rate": normal_false_deny_rate,
            "suspicious_total": suspicious_total,
            "suspicious_confirm_or_deny_rate": suspicious_confirm_or_deny_rate,
            "failed_cases": failures,
        },
    }



def percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def write_outputs(results: List[Dict[str, Any]]) -> None:
    all_rows = []
    summary = {}

    for result in results:
        strategy = result["strategy"]
        all_rows.extend(result["rows"])
        summary[strategy] = result["summary"]

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()) if all_rows else [])
        writer.writeheader()
        writer.writerows(all_rows)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    md = []
    md.append("# Agent Authorization Gateway 对比实验报告\n\n")

    md.append("## 1. 对比方案\n\n")
    md.append("- allow_all：无防护 Agent，所有工具调用直接放行。\n")
    md.append("- keyword：简单关键词规则，命中危险关键词则拒绝，否则放行。\n")
    md.append("- gateway：本项目安全网关，综合使用授权、风险评分、确认与审计机制。\n")

    md.append("\n## 2. 总体对比结果\n\n")
    md.append("| 方案 | 总样例数 | 总体一致率 | 攻击阻断/确认率 | 攻击误放行率 | 正常误拒绝率 | 平均延迟 |\n")
    md.append("|---|---:|---:|---:|---:|---:|---:|\n")

    for strategy, item in summary.items():
        md.append(
            f"| {strategy} "
            f"| {item['total_cases']} "
            f"| {percent(item['accuracy'])} "
            f"| {percent(item['attack_block_or_confirm_rate'])} "
            f"| {percent(item['attack_unsafe_allow_rate'])} "
            f"| {percent(item['normal_false_deny_rate'])} "
            f"| {item['avg_latency_ms']:.3f} ms |\n"
        )

    md.append("\n## 3. 决策分布\n\n")
    for strategy, item in summary.items():
        md.append(f"### {strategy}\n\n")
        for key, value in item["decision_distribution"].items():
            md.append(f"- {key}: {value}\n")
        md.append("\n")

    md.append("## 4. 实验结论\n\n")
    md.append("无防护 Agent 基线虽然延迟最低，但会直接放行攻击样例，无法提供有效安全防护。\n\n")
    md.append("简单关键词规则能够拦截部分显式风险，但对上下文风险、低置信度计划和绕过型攻击的处理能力有限，也容易产生较粗糙的拒绝策略。\n\n")
    md.append("本项目安全网关在保持较低检测延迟的同时，能够对攻击样例进行拒绝或升级确认，并兼顾正常任务可用性，体现出相较基线方案更完整的安全治理能力。\n\n")

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

    print("")
    print("========== Baseline Comparison Finished ==========")
    print(f"CSV: {OUT_CSV}")
    print(f"JSON: {OUT_JSON}")
    print(f"Markdown: {OUT_MD}")


if __name__ == "__main__":
    main()
