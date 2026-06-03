import ast
import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter


router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
TESTS_DIR = BASE_DIR / "tests"
SECURITY_CASES_DIR = BASE_DIR / "security_cases"
EXPERIMENTS_DIR = BASE_DIR / "experiments"
WORKFLOW_FILE = BASE_DIR / ".github" / "workflows" / "ci.yml"


def count_json_array(path: Path) -> int:
    if not path.exists():
        return 0

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return 0

    if isinstance(data, list):
        return len(data)

    return 0


def count_unittest_cases() -> int:
    """
    静态统计 tests 目录下 test_*.py 文件中的 test_ 方法数量。
    这个数字用于展示项目测试规模，不替代真实 unittest 执行结果。
    """
    if not TESTS_DIR.exists():
        return 0

    total = 0

    for file_path in TESTS_DIR.glob("test_*.py"):
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                total += 1

    return total


def file_status(path: Path) -> Dict[str, Any]:
    return {
        "exists": path.exists(),
        "path": str(path.relative_to(BASE_DIR)) if path.exists() else str(path),
    }


@router.get("/security/overview")
def security_overview():
    """
    返回当前系统安全能力概览。
    用于前端安全总览页展示，也方便答辩时快速说明项目完成度。
    """
    gateway_cases_file = SECURITY_CASES_DIR / "gateway_cases.json"
    attack_chain_cases_file = SECURITY_CASES_DIR / "attack_chain_cases.json"

    gateway_report_file = EXPERIMENTS_DIR / "gateway_benchmark_report.md"
    gateway_csv_file = EXPERIMENTS_DIR / "gateway_benchmark_results.csv"

    attack_chain_demo_report_file = EXPERIMENTS_DIR / "attack_chain_demo_report.md"
    attack_chain_demo_json_file = EXPERIMENTS_DIR / "attack_chain_demo_result.json"

    attack_chain_benchmark_report_file = EXPERIMENTS_DIR / "attack_chain_benchmark_report.md"
    attack_chain_benchmark_csv_file = EXPERIMENTS_DIR / "attack_chain_benchmark_results.csv"
    comparison_report_file = EXPERIMENTS_DIR / "comparison_benchmark_report.md"
    comparison_csv_file = EXPERIMENTS_DIR / "comparison_benchmark_results.csv"

    gateway_case_count = count_json_array(gateway_cases_file)
    attack_chain_case_count = count_json_array(attack_chain_cases_file)
    unit_test_count = count_unittest_cases()

    features = [
        {
            "key": "explainable_risk",
            "name": "可解释风险评估",
            "enabled": True,
            "description": "Gateway 返回 risk_level 与 explanations，支持结构化说明风险来源。",
        },
        {
            "key": "task_contract",
            "name": "任务授权合约",
            "enabled": True,
            "description": "限制 Agent 在当前任务中的工具、资源和目标对象访问范围。",
        },
        {
            "key": "capability_contract",
            "name": "Capability Contract 能力约束",
            "enabled": True,
            "description": "支持更细粒度的工具能力、步骤边界和风险预算约束。",
        },
        {
            "key": "audit_hash_chain",
            "name": "审计日志哈希链",
            "enabled": True,
            "description": "审计日志包含 prev_hash 与 record_hash，可检测篡改、删除、插入或重排。",
        },
        {
            "key": "attack_chain_detector",
            "name": "多步攻击链检测",
            "enabled": True,
            "description": "识别外部内容读取、提示注入、敏感资源访问、外部发送和高危命令执行等链式风险。",
        },
        {
            "key": "attack_chain_runtime",
            "name": "运行时攻击链检测",
            "enabled": True,
            "description": "攻击链检测已接入 /attack-chain/check 接口，可参与真实调用流程的最终决策。",
        },
        {
            "key": "gateway_benchmark",
            "name": "网关安全评测",
            "enabled": gateway_case_count > 0,
            "description": "基于 security_cases/gateway_cases.json 自动评测网关安全策略。",
        },
        {
            "key": "attack_chain_benchmark",
            "name": "攻击链批量评测",
            "enabled": attack_chain_case_count > 0,
            "description": "基于 security_cases/attack_chain_cases.json 自动评测攻击链检测能力。",
        },
        {
            "key": "comparison_benchmark",
            "name": "安全对比实验",
            "enabled": comparison_report_file.exists(),
            "description": "对比无防护、单步网关、网关+攻击链检测三种模式的安全效果。",
        },
        {
            "key": "ci",
            "name": "GitHub Actions 自动测试",
            "enabled": WORKFLOW_FILE.exists(),
            "description": "推送后自动运行单元测试、安全评测和攻击链演示。",
        },
    ]

    return {
        "project": "Agent-Authorization",
        "title": "面向 AI Agent 工具调用的授权与安全防护系统",
        "summary": "系统提供工具调用前置授权、动态风险评分、可解释决策、审计防篡改、多步攻击链检测和可复现安全评测能力。",
        "metrics": {
            "unit_test_cases": unit_test_count,
            "gateway_security_cases": gateway_case_count,
            "attack_chain_cases": attack_chain_case_count,
            "total_security_cases": gateway_case_count + attack_chain_case_count,
        },
        "reports": {
            "gateway_benchmark_report": file_status(gateway_report_file),
            "gateway_benchmark_results": file_status(gateway_csv_file),
            "attack_chain_demo_report": file_status(attack_chain_demo_report_file),
            "attack_chain_demo_result": file_status(attack_chain_demo_json_file),
            "attack_chain_benchmark_report": file_status(attack_chain_benchmark_report_file),
            "attack_chain_benchmark_results": file_status(attack_chain_benchmark_csv_file),
            "comparison_benchmark_report": file_status(comparison_report_file),
            "comparison_benchmark_results": file_status(comparison_csv_file),
        },
        "automation": {
            "github_actions_configured": WORKFLOW_FILE.exists(),
            "workflow_file": str(WORKFLOW_FILE.relative_to(BASE_DIR)) if WORKFLOW_FILE.exists() else None,
        },
        "features": features,
    }
