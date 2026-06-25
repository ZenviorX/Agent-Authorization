from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path.cwd()
TEST_DIR = ROOT / "test"
BACKUP_DIR = ROOT / ("legacy_test_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S"))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def backup_path(path: Path) -> None:
    if not path.exists():
        return
    rel = path.relative_to(ROOT)
    target = BACKUP_DIR / rel
    ensure_dir(target.parent)
    if path.is_dir():
        shutil.copytree(path, target, dirs_exist_ok=True)
    else:
        shutil.copy2(path, target)


def move_file(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    backup_path(src)
    ensure_dir(dst.parent)
    if dst.exists():
        backup_path(dst)
        dst.unlink()
    shutil.move(str(src), str(dst))


def move_dir_contents(src_dir: Path, dst_dir: Path, pattern: str = "*") -> None:
    if not src_dir.exists():
        return
    backup_path(src_dir)
    ensure_dir(dst_dir)
    for src in sorted(src_dir.glob(pattern)):
        dst = dst_dir / src.name
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.move(str(src), str(dst))
        else:
            if dst.exists():
                dst.unlink()
            shutil.move(str(src), str(dst))


def remove_empty_dirs(*dirs: Path) -> None:
    for d in dirs:
        try:
            if d.exists() and d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except Exception:
            pass


def migrate_cases() -> None:
    move_dir_contents(ROOT / "security_cases", TEST_DIR / "cases", "*.json")
    remove_empty_dirs(ROOT / "security_cases")


def migrate_old_test_code() -> None:
    move_dir_contents(ROOT / "tests" / "benchmark", TEST_DIR / "legacy" / "tests" / "benchmark", "*.py")
    move_dir_contents(ROOT / "tests" / "dashboard", TEST_DIR / "legacy" / "tests" / "dashboard", "*.py")
    remove_empty_dirs(ROOT / "tests" / "benchmark", ROOT / "tests" / "dashboard", ROOT / "tests")

    experiment_files = [
        "run_strategy_comparison.py",
        "analyze_strategy_errors.py",
        "generate_case_coverage.py",
        "run_external_agent_adapter_eval.py",
        "run_sandbox_policy_eval.py",
        "run_agent_authorization_extension_eval.py",
        "compare_methods.py",
        "runtime_flow_eval.py",
    ]
    for name in experiment_files:
        move_file(ROOT / "experiments" / name, TEST_DIR / "legacy" / "experiments" / name)

    script_files = [
        "run_project_evaluation.ps1",
        "run_strategy_comparison.ps1",
    ]
    for name in script_files:
        move_file(ROOT / "scripts" / name, TEST_DIR / "legacy" / "scripts" / name)


def migrate_results() -> None:
    results_dir = ROOT / "Results"
    archive_dir = TEST_DIR / "results" / "archive"
    if not results_dir.exists():
        return

    patterns = [
        "strategy_comparison*",
        "strategy_error_analysis*",
        "case_coverage*",
        "Result_*.json",
        "Result_*.html",
    ]
    ensure_dir(archive_dir)

    for pattern in patterns:
        for src in sorted(results_dir.glob(pattern)):
            backup_path(src)
            dst = archive_dir / src.name
            if dst.exists():
                dst.unlink()
            shutil.move(str(src), str(dst))


def decouple_backend_from_old_evaluation_routes() -> None:
    main_py = ROOT / "backend" / "main.py"
    if main_py.exists():
        backup_path(main_py)
        text = main_py.read_text(encoding="utf-8")
        text = re.sub(r"^\s*evaluation_result_routes,\s*\n", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*app\.include_router\(evaluation_result_routes\.router\)\s*\n", "", text, flags=re.MULTILINE)
        main_py.write_text(text, encoding="utf-8")

    route_file = ROOT / "backend" / "routes" / "evaluation_result_routes.py"
    move_file(route_file, TEST_DIR / "legacy" / "backend_routes" / "evaluation_result_routes.py")


def replace_ci_with_test_module() -> None:
    ci = ROOT / ".github" / "workflows" / "ci.yml"
    if not ci.exists():
        return

    backup_path(ci)
    ci.write_text(
        """name: CI

on:
  push:
    branches:
      - main
      - improve-risk-policy
  pull_request:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read

jobs:
  test-module:
    name: Independent test module
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements.txt

      - name: Run independent gateway test module
        run: |
          python -m test.run --case-dir test/cases --output-dir test/results

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: agent-authorization-test-results
          path: |
            test/results/**
""",
        encoding="utf-8",
    )


def patch_gitignore() -> None:
    gitignore = ROOT / ".gitignore"
    if not gitignore.exists():
        return

    backup_path(gitignore)
    text = gitignore.read_text(encoding="utf-8")
    block = """

# Independent test module generated outputs
test/results/latest_*.json
test/results/latest_*.csv
test/results/latest_*.md
test/results/latest_*.html
test/results/run_*/
test/results/archive/
!test/results/.gitkeep
"""
    if "Independent test module generated outputs" not in text:
        text = text.rstrip() + block + "\n"
        gitignore.write_text(text, encoding="utf-8")


def main() -> None:
    if not (ROOT / "backend").exists():
        raise SystemExit("Please run this script from the Agent-Authorization repository root.")

    ensure_dir(BACKUP_DIR)
    ensure_dir(TEST_DIR / "cases")
    ensure_dir(TEST_DIR / "results")
    ensure_dir(TEST_DIR / "legacy")

    migrate_cases()
    migrate_old_test_code()
    migrate_results()
    decouple_backend_from_old_evaluation_routes()
    replace_ci_with_test_module()
    patch_gitignore()

    print("=== Test module restructure completed ===")
    print(f"Backup directory: {BACKUP_DIR.name}")
    print("New test module: test/")
    print("Run:")
    print("  python -m test.run")
    print("Latest outputs:")
    print("  test/results/latest_summary.json")
    print("  test/results/latest_cases.json")
    print("  test/results/latest_report.md")
    print("  test/results/latest_dashboard.html")


if __name__ == "__main__":
    main()
