param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

Write-Host "== AgentGuard Competition Evidence Pipeline ==" -ForegroundColor Cyan

Write-Host "`n[1/4] Running offline runtime benchmark..." -ForegroundColor Cyan
python experiments\run_llm_runtime_benchmark.py

Write-Host "`n[2/4] Generating competition evidence pack..." -ForegroundColor Cyan
python experiments\generate_competition_evidence_pack.py

if (-not $SkipTests) {
    Write-Host "`n[3/4] Running key tests..." -ForegroundColor Cyan
    python -m pytest tests\evidence -q
    python -m pytest tests\benchmark\test_llm_runtime_offline_benchmark.py -q
    python -m pytest tests\routes\test_benchmark_dashboard_routes.py -q
} else {
    Write-Host "`n[3/4] Tests skipped." -ForegroundColor Yellow
}

Write-Host "`n[4/4] Done." -ForegroundColor Green
Write-Host "Dashboard: http://127.0.0.1:8000/benchmark-dashboard"
Write-Host "Start server with:"
Write-Host "python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000"
