#!/usr/bin/env bash
set -euo pipefail

mkdir -p .github/workflows tests/dashboard Results

cp -f _dashboard_update/.ci.yml .github/workflows/ci.yml
cp -f _dashboard_update/generate_ci_dashboard.py tests/dashboard/generate_ci_dashboard.py

echo "Files replaced:"
echo "  .github/workflows/ci.yml"
echo "  tests/dashboard/generate_ci_dashboard.py"

echo
echo "Checking .gitignore for Results ignore rules..."
if [ -f .gitignore ]; then
  grep -n "Results" .gitignore || true
fi

echo
echo "Run these commands next:"
echo "  python -m pytest tests -q"
echo "  python tests/dashboard/generate_ci_dashboard.py"
echo "  git status"
