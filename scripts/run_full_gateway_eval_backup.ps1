param(
    [switch]$OpenDashboard
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Agent Authorization Gateway Full Eval" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host ""
Write-Host "[1/3] Running gateway security evaluation..." -ForegroundColor Yellow
python experiments\run_gateway_eval_v2.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "Gateway evaluation failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[2/3] Generating HTML dashboard..." -ForegroundColor Yellow
python experiments\generate_eval_dashboard.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "Dashboard generation failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[3/3] Evaluation artifacts generated:" -ForegroundColor Yellow
Write-Host " - experiments\gateway_eval_v2_results.csv"
Write-Host " - experiments\gateway_eval_v2_summary.json"
Write-Host " - experiments\gateway_eval_v2_report.md"
Write-Host " - experiments\gateway_eval_dashboard.html"

if ($OpenDashboard) {
    Write-Host ""
    Write-Host "Opening dashboard..." -ForegroundColor Green
    Start-Process "experiments\gateway_eval_dashboard.html"
}

Write-Host ""
Write-Host "Full evaluation completed successfully." -ForegroundColor Green
