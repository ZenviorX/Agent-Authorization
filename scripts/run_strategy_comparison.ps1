param(
    [switch]$Open
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = (Get-Location).Path

Write-Host "=== Running strategy comparison: allow_all / keyword_only / gateway ===" -ForegroundColor Cyan

python .\experiments\run_strategy_comparison.py
python .\experiments\analyze_strategy_errors.py

Write-Host "`nGenerated files:" -ForegroundColor Yellow
Write-Host "- Results\strategy_comparison.csv"
Write-Host "- Results\strategy_comparison_summary.json"
Write-Host "- Results\strategy_comparison_report.md"
Write-Host "- Results\strategy_comparison_dashboard.html"
Write-Host "- Results\strategy_error_analysis.json"
Write-Host "- Results\strategy_error_analysis.md"

if ($Open) {
    Start-Process ".\Results\strategy_comparison_dashboard.html"
}
