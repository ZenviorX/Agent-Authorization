param(
    [switch]$OpenDashboard
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Agent Authorization Full Evaluation" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host ""
Write-Host "[1/4] Running gateway security evaluation..." -ForegroundColor Yellow
python experiments\runners\run_gateway_eval_v2.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "Gateway evaluation failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[2/4] Generating gateway evaluation dashboard..." -ForegroundColor Yellow
python experiments\runners\generate_eval_dashboard.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "Gateway dashboard generation failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[3/4] Running baseline comparison experiment..." -ForegroundColor Yellow
python experiments\runners\run_baseline_comparison.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "Baseline comparison failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[4/4] Generating baseline comparison dashboard..." -ForegroundColor Yellow
python experiments\runners\generate_baseline_comparison_dashboard.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "Baseline comparison dashboard generation failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Evaluation artifacts generated:" -ForegroundColor Yellow
Write-Host " - experiments\outputs\gateway_eval_v2_results.csv"
Write-Host " - experiments\outputs\gateway_eval_v2_summary.json"
Write-Host " - experiments\reports\gateway_eval_v2_report.md"
Write-Host " - experiments\dashboards\gateway_eval_dashboard.html"
Write-Host " - experiments\outputs\baseline_comparison_results.csv"
Write-Host " - experiments\outputs\baseline_comparison_summary.json"
Write-Host " - experiments\reports\baseline_comparison_report.md"
Write-Host " - experiments\dashboards\baseline_comparison_dashboard.html"

if ($OpenDashboard) {
    Write-Host ""
    Write-Host "Opening dashboards..." -ForegroundColor Green
    Start-Process "experiments\dashboards\gateway_eval_dashboard.html"
    Start-Process "experiments\dashboards\baseline_comparison_dashboard.html"
}

Write-Host ""
Write-Host "Full evaluation completed successfully." -ForegroundColor Green
