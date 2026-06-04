import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DASHBOARD_SCRIPT = ROOT_DIR / "tests" / "dashboard" / "generate_ci_dashboard.py"
WORKFLOW_FILE = ROOT_DIR / ".github" / "workflows" / "ci.yml"


class TestDashboardBenchmark(unittest.TestCase):
    def test_dashboard_script_exists(self):
        self.assertTrue(
            DASHBOARD_SCRIPT.exists(),
            msg=f"Dashboard script not found: {DASHBOARD_SCRIPT}",
        )

    def test_dashboard_script_outputs_html_artifact(self):
        content = DASHBOARD_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "ci_experiment_dashboard.html",
            content,
        )
        self.assertIn(
            "tests",
            content,
        )
        self.assertIn(
            "artifacts",
            content,
        )

    def test_workflow_uses_dashboard_script(self):
        self.assertTrue(
            WORKFLOW_FILE.exists(),
            msg=f"Workflow file not found: {WORKFLOW_FILE}",
        )

        content = WORKFLOW_FILE.read_text(encoding="utf-8")

        self.assertIn(
            "python tests/dashboard/generate_ci_dashboard.py",
            content,
        )
        self.assertIn(
            "tests/artifacts/ci_experiment_dashboard.html",
            content,
        )


if __name__ == "__main__":
    unittest.main()
