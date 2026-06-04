import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DASHBOARD_SCRIPT = ROOT_DIR / "tests" / "dashboard" / "generate_ci_dashboard.py"
WORKFLOW_FILE = ROOT_DIR / ".github" / "workflows" / "ci.yml"
RESULTS_DIR = ROOT_DIR / "Results"


class TestDashboardBenchmark(unittest.TestCase):
    def test_dashboard_script_exists(self):
        self.assertTrue(
            DASHBOARD_SCRIPT.exists(),
            msg=f"Dashboard script not found: {DASHBOARD_SCRIPT}",
        )

    def test_dashboard_script_outputs_numbered_html_result(self):
        content = DASHBOARD_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("RESULTS_DIR", content)
        self.assertIn("Results", content)
        self.assertIn("Result_", content)
        self.assertIn(".html", content)
        self.assertIn("get_next_result_path", content)

    def test_results_folder_exists(self):
        self.assertTrue(
            RESULTS_DIR.exists(),
            msg=f"Results folder not found: {RESULTS_DIR}",
        )

    def test_workflow_uses_dashboard_script_and_commits_results(self):
        self.assertTrue(
            WORKFLOW_FILE.exists(),
            msg=f"Workflow file not found: {WORKFLOW_FILE}",
        )

        content = WORKFLOW_FILE.read_text(encoding="utf-8")

        self.assertIn(
            "python tests/dashboard/generate_ci_dashboard.py",
            content,
        )
        self.assertIn("Results/Result_*.html", content)
        self.assertIn("git add Results/*.html", content)
        self.assertIn("[skip ci]", content)


if __name__ == "__main__":
    unittest.main()
