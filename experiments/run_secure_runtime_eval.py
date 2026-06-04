import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.runtime.secure_agent_runtime import SecureAgentRuntime


CASE_DIR = PROJECT_ROOT / "security_cases"

OUT_CSV = PROJECT_ROOT / "experiments" / "secure_runtime_results.csv"
OUT_JSON = PROJECT_ROOT / "experiments" / "secure_runtime_summary.json"
OUT_MD = PROJECT_ROOT / "experiments" / "secure_runtime_report.md"


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


def normalize_security_label(case: Dict[str, Any]) -> str:
    category = str(case.get("category", "")).lower()

    if category in {"normal", "benign", "safe"}:
        return "normal"

    if category in {"attack", "malicious", "dangerous"}:
        return "attack"

    return "suspicious"


def prepare_runtime_workspace() -> None:
    """
    ? Secure Runtime ?????????????
    ??????? runtime_workspace ??????????? file.read ???????????
    """
    workspace = PROJECT_ROOT / "runtime_workspace"

    files = {
        "public/readme.md": "This is a public readme file for secure runtime evaluation.\n",
        "public/docs/guide.md": "This is a public guide document for secure runtime evaluation.\n",
        "public/assets/logo.png": "mock image content for secure runtime evaluation.\n",
    }

    for relative_path, content in files.items():
        file_path = workspace / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")





def run_runtime_eval() -> Dict[str, Any]:
    cases = load_cases()
    prepare_runtime_workspace()
    runtime = SecureAgentRuntime()

    rows = []

    decision_counter = Counter()
    execution_status_counter = Counter()
    security_label_counter = Counter()

    total_cases = 0
    executed_cases = 0
    blocked_cases = 0
    confirm_cases = 0

    attack_total = 0
    attack_executed = 0
    attack_not_executed = 0

    normal_total = 0
    normal_executed = 0
    normal_not_executed = 0

    total_elapsed_ms = 0.0

    for case in cases:
        total_cases += 1

        security_label = normalize_security_label(case)
        security_label_counter[security_label] += 1

        if security_label == "attack":
            attack_total += 1
        elif security_label == "normal":
            normal_total += 1

        result = runtime.run_tool_call(case["request"])

        decision = result.get("gateway_decision")
        execution_status = result.get("execution_status")
        elapsed_ms = float(result.get("elapsed_ms", 0))

        total_elapsed_ms += elapsed_ms

        decision_counter[decision] += 1
        execution_status_counter[execution_status] += 1

        did_execute = result.get("execution_result") is not None

        if did_execute:
            executed_cases += 1
        else:
            if execution_status == "waiting_for_human_confirmation":
                confirm_cases += 1
            else:
                blocked_cases += 1

        if security_label == "attack":
            if did_execute:
                attack_executed += 1
            else:
                attack_not_executed += 1

        if security_label == "normal":
            if did_execute:
                normal_executed += 1
            else:
                normal_not_executed += 1

        rows.append(
            {
                "id": case.get("id"),
                "source_file": case.get("_source_file", "unknown"),
                "category": case.get("category", "unknown"),
                "security_label": security_label,
                "description": case.get("description", ""),
                "tool": result.get("tool"),
                "gateway_decision": decision,
                "risk_score": result.get("risk_score"),
                "risk_level": result.get("risk_level"),
                "execution_status": execution_status,
                "did_execute": did_execute,
                "elapsed_ms": round(elapsed_ms, 3),
                "message": result.get("message", ""),
            }
        )

    avg_elapsed_ms = total_elapsed_ms / total_cases if total_cases else 0.0

    summary = {
        "total_cases": total_cases,
        "executed_cases": executed_cases,
        "confirm_cases": confirm_cases,
        "blocked_cases": blocked_cases,
        "execution_rate": executed_cases / total_cases if total_cases else 0.0,
        "confirm_rate": confirm_cases / total_cases if total_cases else 0.0,
        "blocked_rate": blocked_cases / total_cases if total_cases else 0.0,
        "attack_total": attack_total,
        "attack_executed": attack_executed,
        "attack_not_executed": attack_not_executed,
        "attack_execution_rate": attack_executed / attack_total if attack_total else 0.0,
        "attack_not_executed_rate": attack_not_executed / attack_total if attack_total else 0.0,
        "normal_total": normal_total,
        "normal_executed": normal_executed,
        "normal_not_executed": normal_not_executed,
        "normal_execution_rate": normal_executed / normal_total if normal_total else 0.0,
        "normal_not_executed_rate": normal_not_executed / normal_total if normal_total else 0.0,
        "avg_elapsed_ms": avg_elapsed_ms,
        "decision_distribution": dict(decision_counter),
        "execution_status_distribution": dict(execution_status_counter),
        "security_label_distribution": dict(security_label_counter),
    }

    return {
        "rows": rows,
        "summary": summary,
    }



def percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def write_outputs(result: Dict[str, Any]) -> None:
    rows = result["rows"]
    summary = result["summary"]

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    md = []
    md.append("# Secure Agent Runtime 批量评测报告\n\n")

    md.append("## 1. 总体结果\n\n")
    md.append(f"- 总样例数：{summary['total_cases']}\n")
    md.append(f"- 实际执行样例数：{summary['executed_cases']}\n")
    md.append(f"- 进入人工确认样例数：{summary['confirm_cases']}\n")
    md.append(f"- 被网关阻断样例数：{summary['blocked_cases']}\n")
    md.append(f"- 总体执行率：{percent(summary['execution_rate'])}\n")
    md.append(f"- 总体确认率：{percent(summary['confirm_rate'])}\n")
    md.append(f"- 总体阻断率：{percent(summary['blocked_rate'])}\n")
    md.append(f"- 平均运行时耗时：{summary['avg_elapsed_ms']:.3f} ms\n")

    md.append("\n## 2. 攻击样例执行控制\n\n")
    md.append(f"- 攻击样例数：{summary['attack_total']}\n")
    md.append(f"- 攻击样例实际执行数：{summary['attack_executed']}\n")
    md.append(f"- 攻击样例未执行数：{summary['attack_not_executed']}\n")
    md.append(f"- 攻击样例执行率：{percent(summary['attack_execution_rate'])}\n")
    md.append(f"- 攻击样例未执行率：{percent(summary['attack_not_executed_rate'])}\n")

    md.append("\n## 3. 正常样例执行情况\n\n")
    md.append(f"- 正常样例数：{summary['normal_total']}\n")
    md.append(f"- 正常样例实际执行数：{summary['normal_executed']}\n")
    md.append(f"- 正常样例未执行数：{summary['normal_not_executed']}\n")
    md.append(f"- 正常样例执行率：{percent(summary['normal_execution_rate'])}\n")
    md.append(f"- 正常样例未执行率：{percent(summary['normal_not_executed_rate'])}\n")

    md.append("\n## 4. Gateway 决策分布\n\n")
    for key, value in summary["decision_distribution"].items():
        md.append(f"- {key}: {value}\n")

    md.append("\n## 5. 运行时执行状态分布\n\n")
    for key, value in summary["execution_status_distribution"].items():
        md.append(f"- {key}: {value}\n")

    md.append("\n## 6. 实验结论\n\n")
    md.append("Secure Agent Runtime 将 Gateway 安全决策与受控工具执行器连接起来，使 Agent 工具调用不再是单纯的风险评分请求，而是形成了“检查、决策、执行或阻断”的完整运行时链路。\n\n")
    md.append("在该运行时中，只有被 Gateway 判定为 allow 的请求才会进入 SafeToolExecutor 执行；confirm 请求进入人工确认等待；deny 请求被直接阻断，不会触发真实工具执行。\n\n")
    md.append("该结果说明，本项目已经从安全检测模块进一步升级为 Agent 工具调用运行时安全中间层，为后续接入真实 LLM Agent 或 MCP 工具调用提供了基础。\n")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("".join(md))



def main() -> None:
    result = run_runtime_eval()
    write_outputs(result)

    summary = result["summary"]

    print("========== Secure Runtime Eval Finished ==========")
    print(f"Total cases: {summary['total_cases']}")
    print(f"Executed cases: {summary['executed_cases']}")
    print(f"Confirm cases: {summary['confirm_cases']}")
    print(f"Blocked cases: {summary['blocked_cases']}")
    print(f"Attack execution rate: {percent(summary['attack_execution_rate'])}")
    print(f"Attack not executed rate: {percent(summary['attack_not_executed_rate'])}")
    print(f"Normal execution rate: {percent(summary['normal_execution_rate'])}")
    print(f"Average elapsed: {summary['avg_elapsed_ms']:.3f} ms")
    print(f"CSV: {OUT_CSV}")
    print(f"JSON: {OUT_JSON}")
    print(f"Markdown: {OUT_MD}")


if __name__ == "__main__":
    main()
