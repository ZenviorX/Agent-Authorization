import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = ROOT / "security_cases"
VALID_DECISIONS = {"allow", "confirm", "deny", "review"}

def case_files():
    return sorted(CASE_DIR.glob("gateway_cases*.json"))

def load_cases():
    cases = []
    for path in case_files():
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict) and "cases" in data:
            data = data["cases"]
        assert isinstance(data, list), f"{path.name} must be a list or dict with cases"
        for case in data:
            if isinstance(case, dict) and "request" in case:
                item = dict(case)
                item["_source_file"] = path.name
                cases.append(item)
    return cases

def test_security_case_files_exist():
    assert case_files(), "No gateway_cases*.json files found"

def test_security_case_ids_are_unique():
    cases = load_cases()
    ids = [case.get("id") for case in cases]
    assert all(ids), "Every case must have an id"
    duplicates = sorted({x for x in ids if ids.count(x) > 1})
    assert not duplicates, f"Duplicate case ids: {duplicates}"

def test_security_case_required_fields():
    for case in load_cases():
        assert isinstance(case.get("id"), str) and case["id"].strip(), case
        assert isinstance(case.get("category"), str) and case["category"].strip(), case

        request = case.get("request")
        assert isinstance(request, dict), case
        assert isinstance(request.get("user"), str) and request["user"].strip(), case
        assert isinstance(request.get("tool"), str) and request["tool"].strip(), case
        assert isinstance(request.get("params", {}), dict), case

        assert "expected_decision" in case or "expected_decision_in" in case, case

        if "expected_decision" in case:
            assert case["expected_decision"] in VALID_DECISIONS, case

        if "expected_decision_in" in case:
            assert isinstance(case["expected_decision_in"], list) and case["expected_decision_in"], case
            assert set(case["expected_decision_in"]).issubset(VALID_DECISIONS), case

def test_security_case_agent_confidence_range():
    for case in load_cases():
        confidence = case.get("request", {}).get("agent_confidence")
        if confidence is None:
            continue
        assert isinstance(confidence, (int, float)), case
        assert 0 <= confidence <= 1, case

def test_v5_v6_case_files_have_no_mojibake():
    for name in ["gateway_cases_v5_redteam.json", "gateway_cases_v6_redteam.json"]:
        path = CASE_DIR / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8-sig")
        assert "????" not in text, f"{name} contains mojibake question marks"
        assert "\ufffd" not in text, f"{name} contains replacement characters"
