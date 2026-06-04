import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.gateway.gateway import check_tool_call
from backend.schemas import ToolCallRequest


CASE_DIR = PROJECT_ROOT / "security_cases"
OUT_CSV = PROJECT_ROOT / "experiments" / "outputs" / "gateway_eval_v2_results.csv"
OUT_JSON = PROJECT_ROOT / "experiments" / "outputs" / "gateway_eval_v2_summary.json"
OUT_MD = PROJECT_ROOT / "experiments" / "reports" / "gateway_eval_v2_report.md"


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


def run_eval() -> Dict[str, Any]:
    cases = load_cases()
    rows = []
    total_latency = 0.0
    passed = 0
    source_counter = Counter()
    label_counter = Counter()
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
    failures = []

    for case in cases:
        request = ToolCallRequest(**case["request"])
        start = time.perf_counter()
        result = check_tool_call(request)
        latency_ms = (time.perf_counter() - start) * 1000
        total_latency += latency_ms

        decision = result.get("decision")
        risk_score = result.get("risk_score")
        risk_level = result.get("risk_level", "")
        reasons = normalize_list(result.get("reason", []))
        explanations = result.get("explanations", [])
        if not isinstance(explanations, list):
            explanations = []

        ok = expected_match(case, decision)
        source_file = case.get("_source_file", "unknown")
        category = case.get("category", "unknown")
        security_label = normalize_security_label(case)

        source_counter[source_file] += 1
        label_counter[security_label] += 1
        decision_counter[decision] += 1
        category_counter[category] += 1
        category_total[category] += 1

        if ok:
            passed += 1
            category_passed[category] += 1
        else:
            failures.append({
                "id": case.get("id"),
                "source_file": source_file,
                "category": category,
                "description": case.get("description"),
                "expected": case.get("expected_decision", case.get("expected_decision_in")),
                "actual": decision,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "reason": reasons,
            })

        if security_label == "attack":
            attack_total += 1
            if decision in {"deny", "confirm"}:
                attack_blocked_or_confirmed += 1
            if decision == "allow":
                attack_unsafe_allowed += 1
        elif security_label == "normal":
            normal_total += 1
            if decision in {"allow", "confirm"}:
                normal_allowed_or_confirmed += 1
            if decision == "deny":
                normal_denied += 1

        rows.append({
            "id": case.get("id"),
            "source_file": source_file,
            "category": category,
            "security_label": security_label,
            "description": case.get("description"),
            "expected": case.get("expected_decision", case.get("expected_decision_in")),
            "actual": decision,
            "passed": ok,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "latency_ms": round(latency_ms, 3),
            "reason": " | ".join(reasons),
            "explanation_factors": ",".join(sorted({str(item.get("factor", "unknown")) for item in explanations})),
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

    summary = {
        "total_cases": total,
        "passed_cases": passed,
        "accuracy": passed / total if total else 0.0,
        "avg_latency_ms": total_latency / total if total else 0.0,
        "source_file_distribution": dict(source_counter),
        "decision_distribution": dict(decision_counter),
        "security_label_distribution": dict(label_counter),
        "category_distribution": dict(category_counter),
        "category_accuracy": category_accuracy,
        "attack_total": attack_total,
        "attack_block_or_confirm_rate": attack_blocked_or_confirmed / attack_total if attack_total else 0.0,
        "attack_unsafe_allow_rate": attack_unsafe_allowed / attack_total if attack_total else 0.0,
        "normal_total": normal_total,
        "normal_pass_or_confirm_rate": normal_allowed_or_confirmed / normal_total if normal_total else 0.0,
        "normal_false_deny_rate": normal_denied / normal_total if normal_total else 0.0,
        "failed_cases": failures,
    }

    write_outputs(rows, summary)
    return summary


def write_outputs(rows: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    md = []
    md.append("# Agent Authorization Gateway 安全评测报告 V2\n\n")
    md.append("## 1. 总体结果\n\n")
    md.append(f"- 总样例数：{summary['total_cases']}\n")
    md.append(f"- 通过样例数：{summary['passed_cases']}\n")
    md.append(f"- 总体一致率：{summary['accuracy'] * 100:.2f}%\n")
    md.append(f"- 平均检测延迟：{summary['avg_latency_ms']:.3f} ms\n")
    md.append("\n## 2. 攻击拦截能力\n\n")
    md.append(f"- 攻击样例数：{summary['attack_total']}\n")
    md.append(f"- 攻击阻断/升级确认率：{summary['attack_block_or_confirm_rate'] * 100:.2f}%\n")
    md.append(f"- 攻击误放行率：{summary['attack_unsafe_allow_rate'] * 100:.2f}%\n")
    md.append("\n## 3. 正常任务可用性\n\n")
    md.append(f"- 正常样例数：{summary['normal_total']}\n")
    md.append(f"- 正常任务放行/确认率：{summary['normal_pass_or_confirm_rate'] * 100:.2f}%\n")
    md.append(f"- 正常任务误拒绝率：{summary['normal_false_deny_rate'] * 100:.2f}%\n")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("".join(md))


if __name__ == "__main__":
    summary = run_eval()
    print("========== Gateway Eval V2 ==========")
    print(f"Total cases: {summary['total_cases']}")
    print(f"Passed cases: {summary['passed_cases']}")
    print(f"Accuracy: {summary['accuracy'] * 100:.2f}%")
    print(f"CSV: {OUT_CSV}")
    print(f"JSON: {OUT_JSON}")
    print(f"Markdown: {OUT_MD}")
