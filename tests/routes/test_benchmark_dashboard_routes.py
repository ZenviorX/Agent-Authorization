import json

from fastapi.testclient import TestClient

import backend.routes.benchmark_dashboard_routes as benchmark_routes
from backend.main import app


client = TestClient(app)


def test_benchmark_dashboard_route_loads_latest_numbered_report(tmp_path, monkeypatch):
    report_1 = {
        "summary": {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "pass_rate": 1.0,
            "by_category": {"normal": 1},
            "passed_by_category": {"normal": 1},
        },
        "cases": [
            {
                "id": "case_old",
                "category": "normal",
                "description": "old",
                "passed": True,
                "final_decision": "allow",
                "status": "finished",
                "steps": [],
            }
        ],
    }

    report_2 = {
        "summary": {
            "total": 2,
            "passed": 2,
            "failed": 0,
            "pass_rate": 1.0,
            "by_category": {"normal": 1, "attack": 1},
            "passed_by_category": {"normal": 1, "attack": 1},
        },
        "cases": [
            {
                "id": "case_new_normal",
                "category": "normal",
                "description": "new normal",
                "passed": True,
                "final_decision": "allow",
                "status": "finished",
                "steps": [
                    {
                        "step_id": 1,
                        "tool": "file.read",
                        "decision": "allow",
                        "risk_score": 10,
                        "executed": True,
                        "blocked": False,
                        "requires_confirmation": False,
                    }
                ],
            },
            {
                "id": "case_new_attack",
                "category": "attack",
                "description": "new attack",
                "passed": True,
                "final_decision": "deny",
                "status": "blocked",
                "steps": [
                    {
                        "step_id": 1,
                        "tool": "file.read",
                        "decision": "deny",
                        "risk_score": 100,
                        "executed": False,
                        "blocked": True,
                        "requires_confirmation": False,
                    }
                ],
            },
        ],
    }

    (tmp_path / "Result_001.json").write_text(
        json.dumps(report_1, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "Result_002.json").write_text(
        json.dumps(report_2, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(benchmark_routes, "RESULTS_DIR", tmp_path)

    response = client.get("/benchmark/latest")

    assert response.status_code == 200

    data = response.json()
    summary = data["summary"]

    assert summary["report_file"] == "Result_002.json"
    assert summary["total"] == 2
    assert summary["attack_case_count"] == 1
    assert summary["normal_case_count"] == 1
    assert summary["blocked_or_confirmed_attack"] == 1
    assert summary["normal_available"] == 1
    assert len(data["cases"]) == 2


def test_benchmark_dashboard_page_is_available():
    response = client.get("/benchmark-dashboard")

    assert response.status_code == 200
    assert "AgentGuard Benchmark Dashboard" in response.text
