import json
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = PROJECT_ROOT / "security_cases" / "llm_runtime_cases.json"


ALLOWED_CATEGORIES = {
    "normal",
    "attack",
    "suspicious",
}


ALLOWED_TYPES = {
    "stepwise_llm_runtime",
}


REQUIRED_FIELDS = [
    "id",
    "category",
    "type",
    "description",
    "user",
    "user_input",
    "max_steps",
    "risk_budget",
    "expected",
    "evaluation_points",
]


def load_cases() -> List[Dict[str, Any]]:
    assert CASE_PATH.exists(), f"Missing LLM runtime case file: {CASE_PATH}"

    with open(CASE_PATH, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    assert isinstance(data, list), "llm_runtime_cases.json top-level value must be a list"
    assert data, "llm_runtime_cases.json must contain at least one case"

    return data


def test_llm_runtime_cases_have_required_fields():
    cases = load_cases()

    for case in cases:
        case_id = case.get("id", "<missing-id>")

        for field in REQUIRED_FIELDS:
            assert field in case, f"{case_id}: missing required field {field}"


def test_llm_runtime_case_ids_are_unique():
    cases = load_cases()

    ids = [case.get("id") for case in cases]
    duplicated = sorted({case_id for case_id in ids if ids.count(case_id) > 1})

    assert not duplicated, f"Duplicated LLM runtime case ids: {duplicated}"


def test_llm_runtime_cases_have_valid_basic_types():
    cases = load_cases()

    for case in cases:
        case_id = case.get("id", "<missing-id>")

        assert isinstance(case["id"], str) and case["id"].strip(), (
            f"{case_id}: id must be a non-empty string"
        )

        assert case["category"] in ALLOWED_CATEGORIES, (
            f"{case_id}: unsupported category {case['category']}"
        )

        assert case["type"] in ALLOWED_TYPES, (
            f"{case_id}: unsupported type {case['type']}"
        )

        assert isinstance(case["description"], str) and case["description"].strip(), (
            f"{case_id}: description must be a non-empty string"
        )

        assert isinstance(case["user"], str) and case["user"].strip(), (
            f"{case_id}: user must be a non-empty string"
        )

        assert isinstance(case["user_input"], str) and case["user_input"].strip(), (
            f"{case_id}: user_input must be a non-empty string"
        )

        assert isinstance(case["max_steps"], int), (
            f"{case_id}: max_steps must be an integer"
        )

        assert 1 <= case["max_steps"] <= 10, (
            f"{case_id}: max_steps should be between 1 and 10"
        )

        assert isinstance(case["risk_budget"], int), (
            f"{case_id}: risk_budget must be an integer"
        )

        assert 1 <= case["risk_budget"] <= 200, (
            f"{case_id}: risk_budget should be between 1 and 200"
        )

        assert isinstance(case["expected"], dict), (
            f"{case_id}: expected must be an object"
        )

        assert isinstance(case["evaluation_points"], list), (
            f"{case_id}: evaluation_points must be a list"
        )

        assert case["evaluation_points"], (
            f"{case_id}: evaluation_points must not be empty"
        )


def test_attack_cases_expect_blocking_decision():
    cases = load_cases()

    for case in cases:
        case_id = case.get("id", "<missing-id>")

        if case["category"] != "attack":
            continue

        expected = case["expected"]

        final_decision = expected.get("final_decision")
        final_decision_in = expected.get("final_decision_in", [])

        assert (
            final_decision == "deny"
            or "deny" in final_decision_in
        ), f"{case_id}: attack case should expect deny or include deny"


def test_normal_cases_do_not_expect_secret_or_attacker_behavior():
    cases = load_cases()

    for case in cases:
        case_id = case.get("id", "<missing-id>")

        if case["category"] != "normal":
            continue

        expected = case["expected"]

        must_not_send_to = expected.get("must_not_send_to", [])
        must_not_access_resources = expected.get("must_not_access_resources", [])

        assert "attacker@example.com" in must_not_send_to, (
            f"{case_id}: normal cases should explicitly forbid attacker@example.com"
        )

        joined_resources = " ".join(str(item) for item in must_not_access_resources).lower()

        assert "secret" in joined_resources or "../" in joined_resources, (
            f"{case_id}: normal cases should explicitly forbid secret/private/path traversal"
        )


def test_prompt_injection_cases_expect_tainted_labels():
    cases = load_cases()

    prompt_cases = [
        case
        for case in cases
        if "prompt" in case["id"].lower()
        or "injected" in case["user_input"].lower()
        or "injected" in str(case["expected"]).lower()
    ]

    assert prompt_cases, "At least one prompt injection runtime case is required"

    for case in prompt_cases:
        case_id = case.get("id", "<missing-id>")
        expected = case["expected"]

        labels = expected.get("expected_output_labels_after_first_step", [])

        assert (
            "prompt_injection" in labels
            or "tainted" in labels
            or case["category"] == "normal"
        ), f"{case_id}: prompt injection case should expect prompt_injection or tainted label"


def test_runtime_cases_cover_key_security_scenarios():
    cases = load_cases()

    all_text = json.dumps(cases, ensure_ascii=False).lower()

    assert "public/injected_notice.txt" in all_text, (
        "Runtime cases should include public/injected_notice.txt indirect prompt injection"
    )

    assert "attacker@example.com" in all_text, (
        "Runtime cases should include attacker@example.com data exfiltration target"
    )

    assert "secret/password.txt" in all_text, (
        "Runtime cases should include secret/password.txt sensitive resource"
    )

    assert "internal@sdu.edu.cn" in all_text, (
        "Runtime cases should include an internal email scenario for false-positive analysis"
    )