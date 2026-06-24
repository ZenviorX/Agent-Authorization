param(
    [switch]$Full,
    [switch]$Open
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = (Get-Location).Path

Write-Host "=== Agent-Authorization Project Evaluation ===" -ForegroundColor Cyan

Write-Host "`n[1/7] Running security case schema tests..." -ForegroundColor Yellow
python -m pytest tests\benchmark\test_security_case_schema.py -q

Write-Host "`n[2/7] Running gateway red-team regression tests..." -ForegroundColor Yellow
python -m pytest tests\benchmark\test_gateway_redteam_cases.py -q

Write-Host "`n[3/7] Running strategy comparison..." -ForegroundColor Yellow
python .\experiments\run_strategy_comparison.py

Write-Host "`n[4/7] Running strategy error analysis..." -ForegroundColor Yellow
python .\experiments\analyze_strategy_errors.py

Write-Host "`n[5/7] Generating case coverage report..." -ForegroundColor Yellow
python .\experiments\generate_case_coverage.py

if ($Full) {
    Write-Host "`n[6/7] Running full pytest suite..." -ForegroundColor Yellow
    python -m pytest tests -q
} else {
    Write-Host "`n[6/7] Skip full pytest suite. Use -Full to run all tests." -ForegroundColor DarkYellow
}

Write-Host "`n[7/7] Checking frontend build..." -ForegroundColor Yellow
npm --prefix ".\frontend" run build

Write-Host "`nRunning project text check..." -ForegroundColor Yellow
python .\scripts\check_project_text.py

Write-Host "`nGenerated evaluation files:" -ForegroundColor Green
Write-Host "- Results\strategy_comparison_summary.json"
Write-Host "- Results\strategy_comparison_report.md"
Write-Host "- Results\strategy_error_analysis.md"
Write-Host "- Results\case_coverage_summary.json"
Write-Host "- Results\case_coverage_report.md"
Write-Host "- Results\case_coverage_dashboard.html"

if ($Open) {
    Start-Process ".\Results\strategy_comparison_dashboard.html"
    Start-Process ".\Results\case_coverage_dashboard.html"
}

Write-Host "`nDone. Project evaluation finished." -ForegroundColor Green
