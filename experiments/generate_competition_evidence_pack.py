from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.evidence.coverage_matrix import build_coverage_matrix
from backend.evidence.integrity import verify_report_integrity


RESULTS_DIR = PROJECT_ROOT / "Results"


def _extract_index(path: Path) -> Optional[int]:
    stem = path.stem

    if not stem.startswith("Result_"):
        return None

    try:
        return int(stem.split("_", 1)[1])
    except (IndexError, ValueError):
        return None


def find_latest_result_json(results_dir: Path = RESULTS_DIR) -> Path:
    candidates = []

    for path in results_dir.glob("Result_*.json"):
        index = _extract_index(path)

        if index is None:
            continue

        candidates.append((index, path))

    if not candidates:
        raise FileNotFoundError("No Results/Result_XXX.json report found.")

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _load_report(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))

    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")

    return data


def _evidence_pack_paths(report_path: Path, output_dir: Path = RESULTS_DIR) -> tuple[Path, Path]:
    index = _extract_index(report_path)

    if index is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return (
            output_dir / f"EvidencePack_{timestamp}.json",
            output_dir / f"EvidencePack_{timestamp}.md",
        )

    return (
        output_dir / f"EvidencePack_{index:03d}.json",
        output_dir / f"EvidencePack_{index:03d}.md",
    )


def _top_cases(report: Dict[str, Any], limit: int = 8) -> list[Dict[str, Any]]:
    cases = report.get("cases", [])

    if not isinstance(cases, list):
        return []

    def score(case: Dict[str, Any]) -> tuple[int, int, int]:
        category_score = 2 if case.get("category") == "attack" else 1 if case.get("category") == "suspicious" else 0

        graph = case.get("security_graph", {})
        summary = graph.get("summary", {}) if isinstance(graph, dict) else {}
        high_risk = int(summary.get("high_risk_flow_count") or 0) if isinstance(summary, dict) else 0

        decision_score = 2 if case.get("final_decision") == "deny" else 1 if case.get("final_decision") == "confirm" else 0

        return category_score, high_risk, decision_score

    valid_cases = [
        case
        for case in cases
        if isinstance(case, dict)
    ]

    return sorted(valid_cases, key=score, reverse=True)[:limit]


def _safe(value: Any, default: str = "-") -> str:
    if value is None:
        return default

    return str(value)


def build_evidence_pack(report_path: Path) -> Dict[str, Any]:
    report = _load_report(report_path)

    integrity = verify_report_integrity(report)
    coverage = build_coverage_matrix(report)
    effectiveness = report.get("effectiveness", {})
    effectiveness_summary = effectiveness.get("summary", {}) if isinstance(effectiveness, dict) else {}
    report_summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}

    top_cases = _top_cases(report)

    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_report": str(report_path),
        "source_report_file": report_path.name,
        "project": "Agent-Authorization / AgentGuard",
        "executive_summary": {
            "total_cases": report_summary.get("total"),
            "passed": report_summary.get("passed"),
            "failed": report_summary.get("failed"),
            "pass_rate": report_summary.get("pass_rate"),
            "integrity_valid": integrity.get("valid"),
            "coverage_score": coverage["summary"].get("coverage_score"),
            "overall_effectiveness_score": effectiveness_summary.get("overall_effectiveness_score"),
            "attack_neutralization_rate": effectiveness_summary.get("attack_neutralization_rate"),
            "normal_availability_rate": effectiveness_summary.get("normal_availability_rate"),
            "prevented_risky_execution_count": effectiveness_summary.get("prevented_risky_execution_count"),
        },
        "integrity": integrity,
        "coverage": coverage,
        "effectiveness": effectiveness,
        "representative_cases": [
            {
                "id": case.get("id"),
                "category": case.get("category"),
                "description": case.get("description"),
                "passed": case.get("passed"),
                "final_decision": case.get("final_decision"),
                "status": case.get("status"),
                "steps": case.get("steps", []),
                "security_graph_summary": (case.get("security_graph", {}) or {}).get("summary", {}),
                "high_risk_flows": (case.get("security_graph", {}) or {}).get("high_risk_flows", []),
            }
            for case in top_cases
        ],
        "reproducibility": {
            "commands": [
                "python experiments\\run_llm_runtime_benchmark.py",
                "python experiments\\generate_competition_evidence_pack.py",
                "python -m pytest tests -q",
                "python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000",
            ],
            "dashboard": "http://127.0.0.1:8000/benchmark-dashboard",
        },
    }


def render_markdown(pack: Dict[str, Any]) -> str:
    executive = pack["executive_summary"]
    integrity = pack["integrity"]
    coverage = pack["coverage"]
    coverage_summary = coverage["summary"]
    effectiveness = pack.get("effectiveness", {})
    effectiveness_summary = effectiveness.get("summary", {}) if isinstance(effectiveness, dict) else {}

    lines: list[str] = []

    lines.append("# AgentGuard 竞赛证据包")
    lines.append("")
    lines.append(f"- 生成时间：{_safe(pack.get('generated_at'))}")
    lines.append(f"- 来源报告：`{_safe(pack.get('source_report_file'))}`")
    lines.append(f"- 项目：{_safe(pack.get('project'))}")
    lines.append("")

    lines.append("## 1. 核心结论")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|---|---:|")
    lines.append(f"| Benchmark 样例总数 | {_safe(executive.get('total_cases'))} |")
    lines.append(f"| 通过样例数 | {_safe(executive.get('passed'))} |")
    lines.append(f"| 失败样例数 | {_safe(executive.get('failed'))} |")
    lines.append(f"| 通过率 | {_safe(executive.get('pass_rate'))} |")
    lines.append(f"| 证据完整性 | {'通过' if executive.get('integrity_valid') else '未通过'} |")
    lines.append(f"| 防护覆盖评分 | {_safe(executive.get('coverage_score'))} |")
    lines.append(f"| 综合有效性评分 | {_safe(executive.get('overall_effectiveness_score'))} |")
    lines.append(f"| 攻击缓解率 | {_safe(executive.get('attack_neutralization_rate'))} |")
    lines.append(f"| 正常任务可用率 | {_safe(executive.get('normal_availability_rate'))} |")
    lines.append(f"| 阻止危险执行次数 | {_safe(executive.get('prevented_risky_execution_count'))} |")
    lines.append("")

    lines.append("## 2. 证据完整性")
    lines.append("")
    lines.append(f"- 校验结果：{'VALID' if integrity.get('valid') else 'INVALID'}")
    lines.append(f"- Root Hash：`{_safe(integrity.get('root_hash'))}`")
    lines.append(f"- Report Hash：`{_safe(integrity.get('report_hash_without_integrity'))}`")
    lines.append(f"- 覆盖样例数：{_safe(integrity.get('total_cases'))}")
    lines.append("")
    lines.append("校验说明：Benchmark 报告在写入时生成 SHA-256 integrity manifest，包含报告哈希、case 级哈希链与 step 摘要。若报告、样例、步骤或图谱证据被事后篡改，完整性校验将失败。")
    lines.append("")

    lines.append("## 3. 防护覆盖矩阵")
    lines.append("")
    lines.append(f"- 覆盖层数：{coverage_summary.get('covered_layer_count')} / {coverage_summary.get('total_layer_count')}")
    lines.append(f"- 覆盖评分：{coverage_summary.get('coverage_score')}")
    lines.append(f"- 平均每个样例覆盖防护层数：{coverage_summary.get('average_layers_per_case')}")
    lines.append("")
    lines.append("| 防护层 | 说明 | 覆盖样例数 |")
    lines.append("|---|---|---:|")

    for layer, desc in coverage.get("layers", {}).items():
        count = coverage_summary.get("layer_counts", {}).get(layer, 0)
        lines.append(f"| `{layer}` | {desc} | {count} |")

    lines.append("")

    lines.append("## 4. AgentGuard vs Naive Baseline")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|---|---:|")
    lines.append(f"| Attack-like cases | {_safe(effectiveness_summary.get('attack_like_cases'))} |")
    lines.append(f"| Mitigated attack-like cases | {_safe(effectiveness_summary.get('mitigated_attack_like_cases'))} |")
    lines.append(f"| Attack neutralization rate | {_safe(effectiveness_summary.get('attack_neutralization_rate'))} |")
    lines.append(f"| Normal availability rate | {_safe(effectiveness_summary.get('normal_availability_rate'))} |")
    lines.append(f"| High-risk flow mitigation rate | {_safe(effectiveness_summary.get('high_risk_flow_mitigation_rate'))} |")
    lines.append(f"| Baseline risky execution count | {_safe(effectiveness_summary.get('baseline_risky_execution_count'))} |")
    lines.append(f"| Prevented risky execution count | {_safe(effectiveness_summary.get('prevented_risky_execution_count'))} |")
    lines.append("")
    lines.append("解释：Naive baseline 表示普通 Agent 直接执行所有计划工具调用，不进行 Capability Contract、Runtime Monitor、语义检测、数据流图谱和人工确认。AgentGuard 的有效性指标用于量化系统相较于无防护 Agent 的安全收益。")
    lines.append("")

    lines.append("## 5. 代表性样例")
    lines.append("")

    for case in pack.get("representative_cases", []):
        graph_summary = case.get("security_graph_summary", {}) or {}
        lines.append(f"### {case.get('id')}")
        lines.append("")
        lines.append(f"- 类别：{case.get('category')}")
        lines.append(f"- 描述：{case.get('description')}")
        lines.append(f"- 结果：{case.get('final_decision')} / passed={case.get('passed')}")
        lines.append(f"- 图谱摘要：nodes={graph_summary.get('node_count', 0)}, edges={graph_summary.get('edge_count', 0)}, sinks={graph_summary.get('sink_count', 0)}, high-risk flows={graph_summary.get('high_risk_flow_count', 0)}")

        flows = case.get("high_risk_flows", []) or []

        if flows:
            lines.append("- 高风险流：")
            for flow in flows[:3]:
                labels = ", ".join(str(item) for item in flow.get("risky_labels", []))
                lines.append(f"  - {flow.get('source')} -> {flow.get('target')}，tool={flow.get('tool')}，labels={labels}，decision={flow.get('decision')}")
        else:
            lines.append("- 高风险流：无")

        lines.append("")

    lines.append("## 6. 可复现命令")
    lines.append("")

    for command in pack.get("reproducibility", {}).get("commands", []):
        lines.append(f"```powershell\n{command}\n```")

    lines.append("")
    lines.append(f"Dashboard：{pack.get('reproducibility', {}).get('dashboard')}")
    lines.append("")

    lines.append("## 7. 答辩展示建议")
    lines.append("")
    lines.append("建议答辩时按以下顺序展示：")
    lines.append("")
    lines.append("1. 打开 Benchmark Dashboard，展示样例数量、通过率、攻击缓解率和有效性评分。")
    lines.append("2. 打开一个攻击样例的安全图谱，展示污染数据或敏感数据如何流向危险 sink。")
    lines.append("3. 打开完整 HTML 报告，展示 case-level 检查结果。")
    lines.append("4. 展示 EvidencePack 中的完整性哈希，说明报告可验证、防篡改。")
    lines.append("5. 用 Naive Baseline 对比说明 AgentGuard 的实际风险降低效果。")
    lines.append("")

    return "\n".join(lines)


def generate_evidence_pack(
    report_path: Optional[Path] = None,
    output_dir: Path = RESULTS_DIR,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_path or find_latest_result_json(output_dir)
    pack = build_evidence_pack(report_path)

    json_path, md_path = _evidence_pack_paths(report_path, output_dir)

    json_path.write_text(
        json.dumps(pack, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        render_markdown(pack),
        encoding="utf-8",
    )

    return {
        "pack": pack,
        "json_path": json_path,
        "markdown_path": md_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate competition evidence pack from latest benchmark result."
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Optional path to Result_XXX.json. If omitted, use latest Results/Result_XXX.json.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(RESULTS_DIR),
        help="Output directory for EvidencePack_XXX.json/md.",
    )

    args = parser.parse_args()

    result = generate_evidence_pack(
        report_path=Path(args.report) if args.report else None,
        output_dir=Path(args.output_dir),
    )

    pack = result["pack"]
    executive = pack["executive_summary"]

    print("Competition evidence pack generated.")
    print(f"Source report: {pack['source_report_file']}")
    print(f"Markdown: {result['markdown_path']}")
    print(f"JSON: {result['json_path']}")
    print(f"Integrity valid: {executive.get('integrity_valid')}")
    print(f"Coverage score: {executive.get('coverage_score')}")
    print(f"Effectiveness score: {executive.get('overall_effectiveness_score')}")


if __name__ == "__main__":
    main()
