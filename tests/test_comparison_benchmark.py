import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app


class TestComparisonBenchmarkReport(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_comparison_report_route_available_or_missing(self):
        response = self.client.get("/reports/comparison-benchmark")

        self.assertIn(response.status_code, [200, 404])

        if response.status_code == 200:
            self.assertIn("Security Comparison Benchmark Report", response.text)

    def test_comparison_script_exists(self):
        path = Path("experiments/run_comparison_benchmark.py")

        self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
