from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from backend.evidence.integrity import verify_report_integrity
from backend.evidence.graph_renderer import render_security_graph_html


router = APIRouter(
    prefix="/benchmark",
    tags=["Benchmark Dashboard"],
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = PROJECT_ROOT / "Results"


def _extract_result_index(path: Path) -> Optional[int]:
    stem = path.stem

    if not stem.startswith("Result_"):
        return None

    try:
        return int(stem.split("_", 1)[1])
    except (IndexError, ValueError):
        return None


def _load_json_file(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"Failed to read JSON report {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"JSON report {path} must be an object")

    return data


def _is_llm_runtime_benchmark_report(data: Dict[str, Any]) -> bool:
    summary = data.get("summary")
    cases = data.get("cases")

    if not isinstance(summary, dict):
        return False

    if not isinstance(cases, list):
        return False

    required_summary_fields = {
        "total",
        "passed",
        "failed",
        "pass_rate",
    }

    return required_summary_fields <= set(summary.keys())


def list_numbered_json_reports(results_dir: Optional[Path] = None) -> List[Path]:
    results_dir = results_dir or RESULTS_DIR

    if not results_dir.exists():
        return []

    candidates = []

    for path in results_dir.glob("Result_*.json"):
        index = _extract_result_index(path)

        if index is None:
            continue

        candidates.append((index, path))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in candidates]


def find_latest_benchmark_report(results_dir: Optional[Path] = None) -> tuple[Path, Dict[str, Any]]:
    results_dir = results_dir or RESULTS_DIR

    for path in list_numbered_json_reports(results_dir):
        try:
            data = _load_json_file(path)
        except ValueError:
            continue

        if _is_llm_runtime_benchmark_report(data):
            return path, data

    raise FileNotFoundError(
        "No numbered LLM runtime benchmark report found under Results/Result_*.json"
    )


def summarize_case(case: Dict[str, Any]) -> Dict[str, Any]:
    steps = case.get("steps", [])

    if not isinstance(steps, list):
        steps = []

    decisions = [
        str(step.get("decision"))
        for step in steps
        if isinstance(step, dict) and step.get("decision")
    ]

    tools = [
        str(step.get("tool"))
        for step in steps
        if isinstance(step, dict) and step.get("tool")
    ]

    executed_count = sum(
        1
        for step in steps
        if isinstance(step, dict) and step.get("executed") is True
    )

    blocked_count = sum(
        1
        for step in steps
        if isinstance(step, dict) and step.get("blocked") is True
    )

    confirm_count = sum(
        1
        for step in steps
        if isinstance(step, dict) and step.get("requires_confirmation") is True
    )

    graph = case.get("security_graph", {})
    if not isinstance(graph, dict):
        graph = {}

    graph_summary = graph.get("summary", {})
    if not isinstance(graph_summary, dict):
        graph_summary = {}

    high_risk_flows = graph.get("high_risk_flows", [])
    if not isinstance(high_risk_flows, list):
        high_risk_flows = []

    return {
        "id": case.get("id"),
        "category": case.get("category"),
        "description": case.get("description"),
        "passed": bool(case.get("passed")),
        "final_decision": case.get("final_decision"),
        "status": case.get("status"),
        "step_count": len(steps),
        "tools": tools,
        "decisions": decisions,
        "executed_count": executed_count,
        "blocked_count": blocked_count,
        "confirm_count": confirm_count,
        "graph_summary": graph_summary,
        "high_risk_flow_count": graph_summary.get("high_risk_flow_count", 0),
        "sink_count": graph_summary.get("sink_count", 0),
        "tainted_step_count": graph_summary.get("tainted_step_count", 0),
        "sensitive_step_count": graph_summary.get("sensitive_step_count", 0),
        "high_risk_flows_preview": high_risk_flows[:3],
    }


def build_dashboard_payload(report_path: Path, report: Dict[str, Any]) -> Dict[str, Any]:
    summary = dict(report.get("summary", {}))
    cases = report.get("cases", [])

    if not isinstance(cases, list):
        cases = []

    case_cards = [
        summarize_case(case)
        for case in cases
        if isinstance(case, dict)
    ]

    attack_cases = [
        case
        for case in case_cards
        if str(case.get("category")) == "attack"
    ]

    normal_cases = [
        case
        for case in case_cards
        if str(case.get("category")) == "normal"
    ]

    suspicious_cases = [
        case
        for case in case_cards
        if str(case.get("category")) == "suspicious"
    ]

    blocked_or_confirmed_attack = sum(
        1
        for case in attack_cases
        if case.get("final_decision") in {"deny", "confirm"}
    )

    normal_available = sum(
        1
        for case in normal_cases
        if case.get("final_decision") in {"allow", "confirm"}
    )

    integrity_result = verify_report_integrity(report)

    effectiveness = report.get("effectiveness", {})
    if not isinstance(effectiveness, dict):
        effectiveness = {}

    effectiveness_summary = effectiveness.get("summary", {})
    if not isinstance(effectiveness_summary, dict):
        effectiveness_summary = {}

    summary["effectiveness"] = effectiveness_summary

    summary["report_file"] = report_path.name
    summary["report_path"] = str(report_path)
    summary["attack_case_count"] = len(attack_cases)
    summary["normal_case_count"] = len(normal_cases)
    summary["suspicious_case_count"] = len(suspicious_cases)
    summary["blocked_or_confirmed_attack"] = blocked_or_confirmed_attack
    summary["normal_available"] = normal_available
    summary["integrity_valid"] = integrity_result.get("valid")
    summary["integrity_root_hash"] = integrity_result.get("root_hash")
    summary["integrity_report_hash"] = integrity_result.get("report_hash_without_integrity")
    summary["integrity_reason"] = integrity_result.get("reason", [])

    return {
        "message": "Latest LLM runtime benchmark report loaded successfully.",
        "summary": summary,
        "cases": case_cards,
        "integrity": integrity_result,
        "raw_report": report,
    }


@router.get("/reports")
def list_benchmark_reports():
    reports = []

    for path in list_numbered_json_reports():
        try:
            data = _load_json_file(path)
        except ValueError:
            continue

        if not _is_llm_runtime_benchmark_report(data):
            continue

        summary = dict(data.get("summary", {}))
        reports.append(
            {
                "file": path.name,
                "path": str(path),
                "index": _extract_result_index(path),
                "total": summary.get("total"),
                "passed": summary.get("passed"),
                "failed": summary.get("failed"),
                "pass_rate": summary.get("pass_rate"),
                "generated_at": summary.get("generated_at"),
            }
        )

    return {
        "message": "Benchmark reports listed successfully.",
        "count": len(reports),
        "reports": reports,
    }


@router.get("/latest")
def get_latest_benchmark_report():
    try:
        report_path, report = find_latest_benchmark_report()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return build_dashboard_payload(report_path, report)

@router.get("/latest/integrity")
def verify_latest_benchmark_integrity():
    try:
        report_path, report = find_latest_benchmark_report()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "message": "Latest benchmark report integrity verified.",
        "report_file": report_path.name,
        "integrity": verify_report_integrity(report),
    }

@router.get("/latest/graph/{case_id}")
def get_latest_case_security_graph(case_id: str):
    try:
        report_path, report = find_latest_benchmark_report()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    cases = report.get("cases", [])
    if not isinstance(cases, list):
        cases = []

    for case in cases:
        if not isinstance(case, dict):
            continue

        if str(case.get("id")) == case_id:
            return {
                "message": "Case security graph loaded successfully.",
                "report_file": report_path.name,
                "case_id": case_id,
                "security_graph": case.get("security_graph", {}),
            }

    raise HTTPException(
        status_code=404,
        detail=f"Case {case_id} not found in latest benchmark report.",
    )

@router.get("/latest/graph/{case_id}/view", response_class=HTMLResponse)
def view_latest_case_security_graph(case_id: str):
    try:
        report_path, report = find_latest_benchmark_report()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    cases = report.get("cases", [])
    if not isinstance(cases, list):
        cases = []

    for case in cases:
        if not isinstance(case, dict):
            continue

        if str(case.get("id")) == case_id:
            html = render_security_graph_html(
                case.get("security_graph", {}),
                report_file=report_path.name,
                case_id=case_id,
            )
            return HTMLResponse(content=html)

    raise HTTPException(
        status_code=404,
        detail=f"Case {case_id} not found in latest benchmark report.",
    )

@router.get("/latest/effectiveness")
def get_latest_benchmark_effectiveness():
    try:
        report_path, report = find_latest_benchmark_report()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    effectiveness = report.get("effectiveness", {})

    if not isinstance(effectiveness, dict):
        effectiveness = {}

    return {
        "message": "Latest benchmark effectiveness report loaded successfully.",
        "report_file": report_path.name,
        "effectiveness": effectiveness,
    }
