import json
import unittest
from pathlib import Path

from backend.attack_chain import AttackChainDetector


ROOT_DIR = Path(__file__).resolve().parents[2]
CASE_FILE = ROOT_DIR / "security_cases" / "attack_chain_cases.json"


class TestAttackChainBenchmarkCases(unittest.TestCase):
    def test_attack_chain_case_file_exists_and_has_cases(self):
        self.assertTrue(CASE_FILE.exists())

        cases = json.loads(CASE_FILE.read_text(encoding="utf-8-sig"))

        self.assertGreaterEqual(len(cases), 8)

        categories = {case["category"] for case in cases}
        self.assertIn("normal", categories)
        self.assertIn("attack", categories)

    def test_attack_chain_cases_match_expected_decisions(self):
        cases = json.loads(CASE_FILE.read_text(encoding="utf-8-sig"))

        for case in cases:
            detector = AttackChainDetector(session_id=case["id"])
            result = None

            for step in case["steps"]:
                result = detector.add_event(
                    tool=step["tool"],
                    params=step.get("params", {}),
                    gateway_result=step.get("gateway_result", {}),
                )

            final_decision = result["final_decision"]

            if "expected_decision" in case:
                self.assertEqual(
                    final_decision,
                    case["expected_decision"],
                    msg=f"case={case['id']}",
                )

            elif "expected_decision_in" in case:
                self.assertIn(
                    final_decision,
                    case["expected_decision_in"],
                    msg=f"case={case['id']}",
                )


if __name__ == "__main__":
    unittest.main()
