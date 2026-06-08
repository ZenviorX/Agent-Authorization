"""
AgentGuard 方法对比实验计算模块。

本文件只负责计算 no_protection、keyword_filter、single_gateway、
full_system 等方法在同一批安全样例上的表现。

正式展示入口统一使用：
    python tests/dashboard/generate_ci_dashboard.py

生成的 HTML 仪表盘位于：
    Results/Result_*.html

不建议在日常协作中提交 experiments/results/ 下的临时报告。
"""

import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.gateway.gateway import check_tool_call
from backend.schemas import ToolCallRequest


CASE_DIR = PROJECT_ROOT / "security_cases"
RESULT_DIR = PROJECT_ROOT / "experiments" / "results"


RISK_KEYWORDS = [
    "../",
    "..\\",
    "%2e%2e",
    "%252e%252e",
    "/etc/passwd",
    "secret",
    "private",
    ".env",
    "password",
    "passwd",
    "token",
    "credential",
    "credentials",
    "api_key",
    "apikey",
    "private_key",
    "id_rsa",
    "rm -rf",
    "del /s",
    "format",
    "shutdown",
    "reboot",
    "powershell",
    "cmd.exe /c",
    "curl",
    "wget",
    "nc ",
    "netcat",
    "python -c",
    "bash -c",
    "sh -c",
    "drop table",
    "delete from",
    "truncate",
    "union select",
    "update ",
    "insert into",
    "alter table",
    "ignore previous instructions",
    "ignore all previous instructions",
    "bypass authorization",
    "disable safety",
    "disable security",
    "developer mode",
    "you are now admin",
    "reveal system prompt",
    "send to attacker",
    "忽略之前的规则",
    "忽略系统提示",
    "不要遵守安全策略",
    "绕过权限检查",
    "读取敏感文件",
    "把密码发出去",
    "把 token 发出去",
]


def load_gateway_cases() -> List[Dict[str, Any]]:
    cases = []

    for path in sorted(CASE_DIR.glob("gateway_cases*.json")):
        with path.open("r", encoding="utf-8-sig") as f:
            loaded = json.load(f)

        if not isinstance(loaded, list):
            raise ValueError(f"{path} must contain a JSON list.")

        for item in loaded:
            item = dict(item)
            item["_source_file"] = path.name
            cases.append(item)

    if not cases:
        raise RuntimeError("No gateway_cases*.json files found under security_cases/.")

    return cases


def serialize_request(request: Dict[str, Any]) -> str:
    return json.dumps(request, ensure_ascii=False, sort_keys=True).lower()


def expected_match(case: Dict[str, Any], decision: str) -> bool:
    if "expected_decision" in case:
        return decision == case["expected_decision"]

    if "expected_decision_in" in case:
        return decision in case["expected_decision_in"]

    raise ValueError(
        f"case {case.get('id')} misses expected_decision or expected_decision_in"
    )


def security_label(case: Dict[str, Any]) -> str:
    category = str(case.get("category", "")).lower()

    if category in {"normal", "benign", "safe"}:
        return "normal"

    if category in {"attack", "malicious", "dangerous"}:
        return "attack"

    return "suspicious"


def no_protection_decision(case: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "decision": "allow",
        "risk_score": 0,
        "reason": ["baseline: no protection, always allow"],
    }


def keyword_filter_decision(case: Dict[str, Any]) -> Dict[str, Any]:
    request_text = serialize_request(case.get("request", {}))
    matched = [keyword for keyword in RISK_KEYWORDS if keyword.lower() in request_text]

    if matched:
        return {
            "decision": "deny",
            "risk_score": min(100, 20 + 10 * len(matched)),
            "reason": [
                "baseline: keyword filter matched risky keyword(s)",
                ", ".join(matched[:10]),
            ],
        }

    return {
        "decision": "allow",
        "risk_score": 0,
        "reason": ["baseline: keyword filter found no risky keyword"],
    }


def single_gateway_decision(case: Dict[str, Any]) -> Dict[str, Any]:
    raw_request = dict(case["request"])

    # 单步 Gateway 基线：只保留用户、工具和参数。
    # 这样可以观察“没有任务合约、没有数据标签、没有风险预算”时的效果。
    request = ToolCallRequest(
        user=raw_request.get("user", "user"),
        tool=raw_request["tool"],
        params=raw_request.get("params", {}),
        agent_confidence=raw_request.get("agent_confidence"),
        plan_status=raw_request.get("plan_status"),
        plan_warnings=raw_request.get("plan_warnings", []),
    )

    return check_tool_call(request)


def full_system_decision(case: Dict[str, Any]) -> Dict[str, Any]:
    # 完整系统：保留 case 中的所有 ToolCallRequest 字段。
    # 后续当样例中加入 task_contract、input_labels、current_step、used_risk 时，
    # 这里会自动体现 Capability Contract 与数据流上下文的效果。
    request = ToolCallRequest(**case["request"])
    return check_tool_call(request)


METHODS = {
    "no_protection": no_protection_decision,
    "keyword_filter": keyword_filter_decision,
    "single_gateway": single_gateway_decision,
    "full_system": full_system_decision,
}


def evaluate_method(
    method_name: str,
    cases: List[Dict[str, Any]],
) -> Dict[str, Any]:
    method = METHODS[method_name]

    rows = []
    total_latency = 0.0

    passed = 0
    decision_counter = Counter()
    source_counter = Counter()
    category_counter = Counter()

    label_total = defaultdict(int)
    label_passed = defaultdict(int)

    attack_total = 0
    attack_block_or_confirm = 0
    attack_allow = 0
    attack_deny = 0
    attack_confirm = 0

    normal_total = 0
    normal_allow_or_confirm = 0
    normal_deny = 0
    normal_allow = 0
    normal_confirm = 0

    for case in cases:
        started = time.perf_counter()
        result = method(case)
        latency_ms = (time.perf_counter() - started) * 1000
        total_latency += latency_ms

        decision = result.get("decision", "unknown")
        label = security_label(case)
        category = str(case.get("category", "unknown"))

        ok = expected_match(case, decision)

        passed += int(ok)
        decision_counter[decision] += 1
        source_counter[case.get("_source_file", "unknown")] += 1
        category_counter[category] += 1

        label_total[label] += 1
        label_passed[label] += int(ok)

        if label == "attack":
            attack_total += 1

            if decision in {"deny", "confirm"}:
                attack_block_or_confirm += 1

            if decision == "allow":
                attack_allow += 1

            if decision == "deny":
                attack_deny += 1

            if decision == "confirm":
                attack_confirm += 1

        elif label == "normal":
            normal_total += 1

            if decision in {"allow", "confirm"}:
                normal_allow_or_confirm += 1

            if decision == "deny":
                normal_deny += 1

            if decision == "allow":
                normal_allow += 1

            if decision == "confirm":
                normal_confirm += 1

        rows.append(
            {
                "id": case.get("id"),
                "source_file": case.get("_source_file"),
                "category": category,
                "security_label": label,
                "expected": case.get(
                    "expected_decision",
                    case.get("expected_decision_in"),
                ),
                "actual": decision,
                "passed": ok,
                "risk_score": result.get("risk_score", 0),
                "latency_ms": round(latency_ms, 4),
                "reason": result.get("reason", []),
            }
        )

    total = len(cases)

    return {
        "method": method_name,
        "summary": {
            "total_cases": total,
            "passed_cases": passed,
            "failed_cases": total - passed,
            "accuracy": passed / total if total else 0.0,
            "avg_latency_ms": total_latency / total if total else 0.0,
            "decision_distribution": dict(decision_counter),
            "source_distribution": dict(source_counter),
            "category_distribution": dict(category_counter),
            "label_accuracy": {
                label: {
                    "total": count,
                    "passed": label_passed[label],
                    "accuracy": label_passed[label] / count if count else 0.0,
                }
                for label, count in sorted(label_total.items())
            },
            "attack_total": attack_total,
            "attack_block_or_confirm_rate": (
                attack_block_or_confirm / attack_total if attack_total else 0.0
            ),
            "attack_unsafe_allow_rate": (
                attack_allow / attack_total if attack_total else 0.0
            ),
            "attack_deny_rate": attack_deny / attack_total if attack_total else 0.0,
            "attack_confirm_rate": (
                attack_confirm / attack_total if attack_total else 0.0
            ),
            "normal_total": normal_total,
            "normal_allow_or_confirm_rate": (
                normal_allow_or_confirm / normal_total if normal_total else 0.0
            ),
            "normal_false_deny_rate": (
                normal_deny / normal_total if normal_total else 0.0
            ),
            "normal_allow_rate": normal_allow / normal_total if normal_total else 0.0,
            "normal_confirm_rate": (
                normal_confirm / normal_total if normal_total else 0.0
            ),
        },
        "rows": rows,
    }


def fmt_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def render_markdown(report: Dict[str, Any]) -> str:
    lines = []

    lines.append("# AgentGuard 对比实验报告")
    lines.append("")
    lines.append(f"- 生成时间：{report['generated_at']}")
    lines.append(f"- 样例来源：`security_cases/gateway_cases*.json`")
    lines.append(f"- 总样例数：{report['total_cases']}")
    lines.append("")

    lines.append("## 1. 方法说明")
    lines.append("")
    lines.append("| 方法 | 含义 |")
    lines.append("|---|---|")
    lines.append("| no_protection | 无防护基线，所有工具调用直接 allow |")
    lines.append("| keyword_filter | 关键词过滤基线，命中危险关键词则 deny |")
    lines.append("| single_gateway | 单步授权网关，只检查当前工具调用 |")
    lines.append("| full_system | 完整系统，保留任务合约、数据标签、步骤和风险预算等上下文 |")
    lines.append("")

    lines.append("## 2. 核心指标对比")
    lines.append("")
    lines.append(
        "| 方法 | 总体一致率 | 攻击阻断/确认率 | 风险误放行率 | 正常误拒率 | 平均延迟 |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|")

    for method_result in report["methods"]:
        name = method_result["method"]
        summary = method_result["summary"]

        lines.append(
            "| "
            + name
            + " | "
            + fmt_percent(summary["accuracy"])
            + " | "
            + fmt_percent(summary["attack_block_or_confirm_rate"])
            + " | "
            + fmt_percent(summary["attack_unsafe_allow_rate"])
            + " | "
            + fmt_percent(summary["normal_false_deny_rate"])
            + " | "
            + f"{summary['avg_latency_ms']:.4f} ms"
            + " |"
        )

    lines.append("")
    lines.append("## 3. 决策分布")
    lines.append("")

    for method_result in report["methods"]:
        name = method_result["method"]
        summary = method_result["summary"]
        lines.append(f"### {name}")
        lines.append("")
        lines.append("```json")
        lines.append(
            json.dumps(
                summary["decision_distribution"],
                ensure_ascii=False,
                indent=2,
            )
        )
        lines.append("```")
        lines.append("")

    lines.append("## 4. 说明")
    lines.append("")
    lines.append(
        "本实验用于对比不同防护强度下的安全效果。"
        "其中 no_protection 和 keyword_filter 作为基础基线，"
        "single_gateway 用于衡量单步工具调用授权效果，"
        "full_system 用于后续评估 Capability Contract、数据标签和风险预算等上下文能力。"
    )
    lines.append("")
    lines.append(
        "后续可继续扩展带有 task_contract、input_labels、current_step、used_risk 的样例，"
        "使 full_system 与 single_gateway 的差异更加明显。"
    )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    cases = load_gateway_cases()

    method_results = []

    for method_name in METHODS:
        print(f"Running method: {method_name}")
        method_results.append(evaluate_method(method_name, cases))

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    report = {
        "generated_at": generated_at,
        "total_cases": len(cases),
        "methods": method_results,
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = RESULT_DIR / f"compare_methods_{timestamp}.json"
    md_path = RESULT_DIR / f"compare_methods_{timestamp}.md"

    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md_path.write_text(
        render_markdown(report),
        encoding="utf-8",
    )

    print("")
    print("Compare methods report generated:")
    print(f"- {json_path.relative_to(PROJECT_ROOT)}")
    print(f"- {md_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()