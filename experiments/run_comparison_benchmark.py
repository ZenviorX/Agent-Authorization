import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from backend.attack_chain import AttackChainDetector
from backend.gateway.gateway import check_tool_call
from backend.schemas import ToolCallRequest


CASE_FILE = ROOT_DIR / "security_cases" / "attack_chain_cases.json"
RESULT_FILE = ROOT_DIR / "experiments" / "comparison_benchmark_results.csv"
REPORT_FILE = ROOT_DIR / "experiments" / "comparison_benchmark_report.md"


def load_cases() -> List[Dict[str, Any]]:
    return json.loads(CASE_FILE.read_text(encoding="utf-8-sig"))


def severity(decision: str) -> int:
    return {
        "allow": 0,
        "confirm": 1,
        "deny": 2,
    }.get(decision, 2)


def stricter_decision(a: str, b: str) -> str:
    if max(severity(a), severity(b)) == 2:
        return "deny"
    if max(severity(a), severity(b)) == 1:
        return "confirm"
    return "allow"


def is_safe_for_case(case: Dict[str, Any], decision: str) -> bool:
    """
    对 normal 样例：allow / confirm 都视为可接受，deny 视为过度拦截。
    对 attack 样例：confirm / deny 都视为成功防护，allow 视为攻击放行。
    """
    if case["category"] == "normal":
        return decision in ["allow", "confirm"]

    if case["category"] == "attack":
        return decision in ["confirm", "deny"]

    return False


def run_baseline(case: Dict[str, Any]) -> Dict[str, Any]:
    """
    无防护基线：所有工具调用默认 allow。
    """
    return {
        "decision": "allow",
        "risk": 0,
        "blocked_or_escalated": False,
    }


def run_gateway_only(case: Dict[str, Any]) -> Dict[str, Any]:
    """
    只使用单步 Gateway。
    多步任务中只要任意一步被 confirm / deny，就认为该链路被升级或阻断。
    """
    final_decision = "allow"
    total_risk = 0
    step_decisions = []

    for step in case["steps"]:
        request = ToolCallRequest(
            user="student",
            tool=step["tool"],
            params=step.get("params", {}),
        )

        result = check_tool_call(request)
        decision = result.get("decision", "deny")
        risk_score = int(result.get("risk_score", 0) or 0)

        step_decisions.append(decision)
        total_risk += risk_score
        final_decision = stricter_decision(final_decision, decision)

    return {
        "decision": final_decision,
        "risk": total_risk,
        "step_decisions": " | ".join(step_decisions),
        "blocked_or_escalated": final_decision in ["confirm", "deny"],
    }


def run_gateway_plus_attack_chain(case: Dict[str, Any]) -> Dict[str, Any]:
    """
    使用 Gateway + AttackChainDetector。
    先用 Gateway 进行单步判断，再把结果输入攻击链检测器进行会话级风险累积。
    """
    detector = AttackChainDetector(session_id=case["id"])
    effective_decision = "allow"
    total_gateway_risk = 0
    step_decisions = []
    chain_stages = []

    for step in case["steps"]:
        request = ToolCallRequest(
            user="student",
            tool=step["tool"],
            params=step.get("params", {}),
        )

        gateway_result = check_tool_call(request)
        gateway_decision = gateway_result.get("decision", "deny")
        total_gateway_risk += int(gateway_result.get("risk_score", 0) or 0)

        chain_result = detector.add_event(
            tool=gateway_result.get("normalized_tool", step["tool"]),
            params=gateway_result.get("normalized_params", step.get("params", {})),
            gateway_result=gateway_result,
        )

        chain_decision = chain_result.get("final_decision", "deny")
        effective_decision = stricter_decision(gateway_decision, chain_decision)

        step_decisions.append(f"{gateway_decision}->{chain_decision}")

        if chain_result.get("events"):
            chain_stages.append(chain_result["events"][-1].get("stage", "unknown"))

    return {
        "decision": effective_decision,
        "risk": total_gateway_risk + int(detector.state.cumulative_risk),
        "step_decisions": " | ".join(step_decisions),
        "chain_stages": " | ".join(chain_stages),
        "cumulative_chain_risk": detector.state.cumulative_risk,
        "blocked_or_escalated": effective_decision in ["confirm", "deny"],
    }


def rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def write_report(rows: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    lines = []

    lines.append("# Security Comparison Benchmark Report")
    lines.append("")
    lines.append("## 1. Overview")
    lines.append("")
    lines.append("This report compares three security settings for AI Agent tool-call workflows:")
    lines.append("")
    lines.append("1. **Baseline**: no protection, all tool calls are allowed.")
    lines.append("2. **Gateway-only**: each tool call is checked independently by the authorization gateway.")
    lines.append("3. **Gateway + AttackChain**: gateway decisions are further enhanced by session-level attack-chain detection.")
    lines.append("")

    lines.append("## 2. Summary Metrics")
    lines.append("")
    lines.append("| Metric | Baseline | Gateway-only | Gateway + AttackChain |")
    lines.append("|---|---:|---:|---:|")
    lines.append(
        f"| Normal workflow acceptance | {summary['baseline_normal_acceptance']:.2%} | "
        f"{summary['gateway_normal_acceptance']:.2%} | "
        f"{summary['full_normal_acceptance']:.2%} |"
    )
    lines.append(
        f"| Attack workflow protection | {summary['baseline_attack_protection']:.2%} | "
        f"{summary['gateway_attack_protection']:.2%} | "
        f"{summary['full_attack_protection']:.2%} |"
    )
    lines.append(
        f"| Overall safe decision rate | {summary['baseline_safe_rate']:.2%} | "
        f"{summary['gateway_safe_rate']:.2%} | "
        f"{summary['full_safe_rate']:.2%} |"
    )

    lines.append("")
    lines.append("## 3. Case-level Results")
    lines.append("")
    lines.append("| ID | Category | Baseline | Gateway-only | Gateway + AttackChain | Chain Risk |")
    lines.append("|---|---|---|---|---|---:|")

    for row in rows:
        lines.append(
            f"| {row['id']} | {row['category']} | {row['baseline_decision']} | "
            f"{row['gateway_decision']} | {row['full_decision']} | {row['full_chain_risk']} |"
        )

    lines.append("")
    lines.append("## 4. Interpretation")
    lines.append("")
    lines.append(
        "The baseline setting allows every tool call, so attack workflows are not protected. "
        "The gateway-only setting can block or escalate obvious single-step risks such as secret file access, external email sending, or dangerous commands. "
        "The Gateway + AttackChain setting further accumulates session-level risk and is able to represent multi-step malicious workflows more explicitly."
    )
    lines.append("")
    lines.append(
        "This comparison provides quantitative evidence that the project is not merely a static rule checker. "
        "It combines single-step authorization with context-aware attack-chain detection to improve protection against chained Agent behaviors."
    )
    lines.append("")

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    cases = load_cases()

    rows = []

    normal_cases = [case for case in cases if case["category"] == "normal"]
    attack_cases = [case for case in cases if case["category"] == "attack"]

    counters = {
        "baseline_safe": 0,
        "gateway_safe": 0,
        "full_safe": 0,
        "baseline_normal_accept": 0,
        "gateway_normal_accept": 0,
        "full_normal_accept": 0,
        "baseline_attack_protect": 0,
        "gateway_attack_protect": 0,
        "full_attack_protect": 0,
    }

    for case in cases:
        baseline = run_baseline(case)
        gateway = run_gateway_only(case)
        full = run_gateway_plus_attack_chain(case)

        baseline_safe = is_safe_for_case(case, baseline["decision"])
        gateway_safe = is_safe_for_case(case, gateway["decision"])
        full_safe = is_safe_for_case(case, full["decision"])

        counters["baseline_safe"] += int(baseline_safe)
        counters["gateway_safe"] += int(gateway_safe)
        counters["full_safe"] += int(full_safe)

        if case["category"] == "normal":
            counters["baseline_normal_accept"] += int(baseline["decision"] in ["allow", "confirm"])
            counters["gateway_normal_accept"] += int(gateway["decision"] in ["allow", "confirm"])
            counters["full_normal_accept"] += int(full["decision"] in ["allow", "confirm"])

        if case["category"] == "attack":
            counters["baseline_attack_protect"] += int(baseline["decision"] in ["confirm", "deny"])
            counters["gateway_attack_protect"] += int(gateway["decision"] in ["confirm", "deny"])
            counters["full_attack_protect"] += int(full["decision"] in ["confirm", "deny"])

        rows.append({
            "id": case["id"],
            "category": case["category"],
            "description": case["description"],
            "baseline_decision": baseline["decision"],
            "gateway_decision": gateway["decision"],
            "full_decision": full["decision"],
            "baseline_safe": baseline_safe,
            "gateway_safe": gateway_safe,
            "full_safe": full_safe,
            "gateway_step_decisions": gateway.get("step_decisions", ""),
            "full_step_decisions": full.get("step_decisions", ""),
            "full_chain_stages": full.get("chain_stages", ""),
            "full_chain_risk": full.get("cumulative_chain_risk", 0),
        })

    total = len(cases)
    normal_total = len(normal_cases)
    attack_total = len(attack_cases)

    summary = {
        "baseline_safe_rate": rate(counters["baseline_safe"], total),
        "gateway_safe_rate": rate(counters["gateway_safe"], total),
        "full_safe_rate": rate(counters["full_safe"], total),
        "baseline_normal_acceptance": rate(counters["baseline_normal_accept"], normal_total),
        "gateway_normal_acceptance": rate(counters["gateway_normal_accept"], normal_total),
        "full_normal_acceptance": rate(counters["full_normal_accept"], normal_total),
        "baseline_attack_protection": rate(counters["baseline_attack_protect"], attack_total),
        "gateway_attack_protection": rate(counters["gateway_attack_protect"], attack_total),
        "full_attack_protection": rate(counters["full_attack_protect"], attack_total),
    }

    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with RESULT_FILE.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "category",
                "description",
                "baseline_decision",
                "gateway_decision",
                "full_decision",
                "baseline_safe",
                "gateway_safe",
                "full_safe",
                "gateway_step_decisions",
                "full_step_decisions",
                "full_chain_stages",
                "full_chain_risk",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    write_report(rows, summary)

    print("========== Security Comparison Benchmark ==========")
    print(f"Total cases: {total}")
    print(f"Normal cases: {normal_total}")
    print(f"Attack cases: {attack_total}")
    print("")
    print(f"Baseline safe decision rate: {summary['baseline_safe_rate']:.2%}")
    print(f"Gateway-only safe decision rate: {summary['gateway_safe_rate']:.2%}")
    print(f"Gateway + AttackChain safe decision rate: {summary['full_safe_rate']:.2%}")
    print("")
    print(f"Baseline attack protection: {summary['baseline_attack_protection']:.2%}")
    print(f"Gateway-only attack protection: {summary['gateway_attack_protection']:.2%}")
    print(f"Gateway + AttackChain attack protection: {summary['full_attack_protection']:.2%}")
    print("")
    print(f"CSV result file: {RESULT_FILE}")
    print(f"Markdown report file: {REPORT_FILE}")


if __name__ == "__main__":
    main()
