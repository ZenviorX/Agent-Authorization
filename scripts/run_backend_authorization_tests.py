from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TESTS = [
    "tests/test_research_oauth_comparison.py",
    "tests/test_research_strategy_comparison.py",
    "tests/test_authorization_trace.py",
    "tests/test_capability_contract.py",
    "tests/test_data_provenance_guard.py",
    "tests/test_capability_token.py",
    "tests/test_capability_token_enforcement.py",
    "tests/test_capability_token_task_binding.py",
    "tests/test_capability_token_execution_gate.py",
    "tests/test_capability_token_execution_positive.py",
    "tests/test_capability_token_issue_policy.py",
    "tests/test_two_phase_tool_proxy_service.py",
    "tests/test_two_phase_tool_proxy_routes.py",
    "tests/test_capability_token_param_binding.py",
    "tests/test_capability_token_tool_binding.py",
    "tests/test_capability_token_expiry.py",
    "tests/test_capability_token_replay_guard.py",
    "tests/test_capability_token_ledger.py",
    "tests/test_capability_token_status_routes.py",
    "tests/test_capability_token_revoke_routes.py",
    "tests/test_capability_token_events_routes.py",
    "tests/test_capability_token_trace_status.py",
    "tests/test_execute_phase_no_new_token.py",
    "tests/test_capability_token_sandbox_binding.py",
    "tests/test_sandbox_path_policy.py",
]

def main() -> int:
    cmd = [sys.executable, "-m", "pytest", *TESTS, "-q"]
    print("=== AgentGuard Backend Authorization Regression ===")
    print("tests:", len(TESTS))
    return subprocess.call(cmd, cwd=ROOT)

if __name__ == "__main__":
    raise SystemExit(main())
