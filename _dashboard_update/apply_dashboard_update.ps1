# Apply AgentGuard dashboard redesign.
# Run this script from the repository root.

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path ".github/workflows" | Out-Null
New-Item -ItemType Directory -Force -Path "tests/dashboard" | Out-Null
New-Item -ItemType Directory -Force -Path "Results" | Out-Null

Copy-Item -Force ".\_dashboard_update\.ci.yml" ".\.github\workflows\ci.yml"
Copy-Item -Force ".\_dashboard_update\generate_ci_dashboard.py" ".\tests\dashboard\generate_ci_dashboard.py"

Write-Host "Files replaced:"
Write-Host "  .github/workflows/ci.yml"
Write-Host "  tests/dashboard/generate_ci_dashboard.py"

Write-Host ""
Write-Host "Checking .gitignore for Results ignore rules..."
if (Test-Path ".gitignore") {
    Select-String -Path ".gitignore" -Pattern "Results" -SimpleMatch | ForEach-Object {
        Write-Host "WARNING: .gitignore contains Results rule:" $_.Line
    }
}

Write-Host ""
Write-Host "Run these commands next:"
Write-Host "  python -m pytest tests -q"
Write-Host "  python tests/dashboard/generate_ci_dashboard.py"
Write-Host "  git status"
