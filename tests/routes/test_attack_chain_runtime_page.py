import unittest

from fastapi.testclient import TestClient

from backend.main import app


class TestAttackChainRuntimePage(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_attack_chain_runtime_page_available(self):
        response = self.client.get("/attack-chain-runtime")

        self.assertEqual(response.status_code, 200)
        self.assertIn("运行时攻击链检测演示", response.text)
        self.assertIn("effective_decision", response.text)
        self.assertIn("demo-runtime-session", response.text)


if __name__ == "__main__":
    unittest.main()
