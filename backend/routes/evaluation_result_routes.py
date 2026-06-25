import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter(prefix="/evaluation", tags=["evaluation"])

BASE_DIR = Path(__file__).resolve().parents[2]
SUMMARY_PATH = BASE_DIR / "Results" / "strategy_comparison_summary.json"
REPORT_PATH = BASE_DIR / "Results" / "strategy_comparison_report.md"
DASHBOARD_PATH = BASE_DIR / "Results" / "strategy_comparison_dashboard.html"


@router.get("/strategy-comparison")
def get_strategy_comparison():
    if not SUMMARY_PATH.exists():
        return {
            "available": False,
            "message": "Strategy comparison result is not generated yet.",
            "hint": "Run scripts/run_strategy_comparison.ps1 first.",
            "total_cases": 0,
            "total_records": 0,
            "elapsed_ms": 0,
            "summary": {},
            "outputs": {},
        }

    try:
        data = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "available": False,
            "message": "Failed to read strategy comparison summary.",
            "error": str(exc),
            "total_cases": 0,
            "total_records": 0,
            "elapsed_ms": 0,
            "summary": {},
            "outputs": {},
        }

    data["available"] = True
    return data


@router.get("/strategy-comparison/report")
def get_strategy_comparison_report():
    if not REPORT_PATH.exists():
        return {
            "available": False,
            "message": "Strategy comparison report is not generated yet.",
            "hint": "Run scripts/run_strategy_comparison.ps1 first.",
        }

    return FileResponse(REPORT_PATH, media_type="text/markdown")


@router.get("/strategy-comparison/dashboard")
def get_strategy_comparison_dashboard():
    if not DASHBOARD_PATH.exists():
        return {
            "available": False,
            "message": "Strategy comparison dashboard is not generated yet.",
            "hint": "Run scripts/run_strategy_comparison.ps1 first.",
        }

    return FileResponse(DASHBOARD_PATH, media_type="text/html")
