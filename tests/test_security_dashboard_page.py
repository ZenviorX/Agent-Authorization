import unittest

from fastapi.testclient import TestClient

from backend.main import app


class TestSecurityDashboardPage(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_security_dashboard_page_available(self):
        response = self.client.get("/security-dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AgentGuard 安全总览", response.text)
        self.assertIn("审计哈希链状态", response.text)
        self.assertIn("网关安全评测报告", response.text)
        self.assertIn("多步攻击链报告", response.text)


if __name__ == "__main__":
    unittest.main()
