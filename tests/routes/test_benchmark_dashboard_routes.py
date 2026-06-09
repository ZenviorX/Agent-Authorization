import json

from fastapi.testclient import TestClient

import backend.routes.benchmark_dashboard_routes as benchmark_routes
from backend.evidence.integrity import attach_integrity_manifest
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
                "security_graph": {
                    "summary": {
                        "node_count": 2,
                        "edge_count": 1,
                        "high_risk_flow_count": 0,
                        "sink_count": 0,
                        "tainted_step_count": 0,
                        "sensitive_step_count": 0
                    },
                    "nodes": [],
                    "edges": [],
                    "high_risk_flows": []
                },
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
        json.dumps(attach_integrity_manifest(report_1), ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "Result_002.json").write_text(
        json.dumps(attach_integrity_manifest(report_2), ensure_ascii=False),
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
    assert summary["integrity_valid"] is True
    assert summary["integrity_root_hash"]
    assert len(data["cases"]) == 2


def test_benchmark_dashboard_page_is_available():
    response = client.get("/benchmark-dashboard")

    assert response.status_code == 200
    assert "AgentGuard Benchmark Dashboard" in response.text



def test_latest_benchmark_integrity_endpoint_verifies_report(tmp_path, monkeypatch):
    report = {
        "summary": {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "pass_rate": 1.0,
            "by_category": {"attack": 1},
            "passed_by_category": {"attack": 1},
        },
        "cases": [
            {
                "id": "attack_case",
                "category": "attack",
                "description": "attack",
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
            }
        ],
    }

    (tmp_path / "Result_010.json").write_text(
        json.dumps(attach_integrity_manifest(report), ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(benchmark_routes, "RESULTS_DIR", tmp_path)

    response = client.get("/benchmark/latest/integrity")

    assert response.status_code == 200

    data = response.json()

    assert data["report_file"] == "Result_010.json"
    assert data["integrity"]["valid"] is True
    assert data["integrity"]["root_hash"]



def test_latest_benchmark_case_security_graph_endpoint(tmp_path, monkeypatch):
    report = {
        "summary": {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "pass_rate": 1.0,
            "by_category": {"attack": 1},
            "passed_by_category": {"attack": 1},
        },
        "cases": [
            {
                "id": "graph_case",
                "category": "attack",
                "description": "graph case",
                "passed": True,
                "final_decision": "confirm",
                "status": "confirm_required",
                "steps": [
                    {
                        "step_id": 1,
                        "tool": "file.read",
                        "decision": "allow",
                        "risk_score": 10,
                        "executed": True,
                        "blocked": False,
                        "requires_confirmation": False,
                        "output_labels": ["public", "tainted"],
                    },
                    {
                        "step_id": 2,
                        "tool": "email.send",
                        "decision": "confirm",
                        "risk_score": 60,
                        "executed": False,
                        "blocked": False,
                        "requires_confirmation": True,
                        "input_from_steps": [1],
                        "input_labels": ["tainted"],
                    },
                ],
                "security_graph": {
                    "summary": {
                        "node_count": 3,
                        "edge_count": 1,
                        "high_risk_flow_count": 1,
                        "sink_count": 1,
                        "tainted_step_count": 2,
                        "sensitive_step_count": 0
                    },
                    "nodes": [{"id": "case:graph_case"}],
                    "edges": [{"source": "step:1", "target": "step:2"}],
                    "high_risk_flows": [{"tool": "email.send"}]
                },
            }
        ],
    }

    (tmp_path / "Result_011.json").write_text(
        json.dumps(attach_integrity_manifest(report), ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(benchmark_routes, "RESULTS_DIR", tmp_path)

    latest_response = client.get("/benchmark/latest")
    assert latest_response.status_code == 200
    assert latest_response.json()["cases"][0]["graph_summary"]["high_risk_flow_count"] == 1

    graph_response = client.get("/benchmark/latest/graph/graph_case")
    assert graph_response.status_code == 200
    assert graph_response.json()["security_graph"]["summary"]["high_risk_flow_count"] == 1



def test_latest_benchmark_case_security_graph_view_endpoint(tmp_path, monkeypatch):
    report = {
        "summary": {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "pass_rate": 1.0,
            "by_category": {"attack": 1},
            "passed_by_category": {"attack": 1},
        },
        "cases": [
            {
                "id": "visual_graph_case",
                "category": "attack",
                "description": "visual graph case",
                "passed": True,
                "final_decision": "confirm",
                "status": "confirm_required",
                "steps": [
                    {
                        "step_id": 1,
                        "tool": "file.read",
                        "decision": "allow",
                        "risk_score": 10,
                        "executed": True,
                        "blocked": False,
                        "requires_confirmation": False,
                        "output_labels": ["tainted"],
                    },
                    {
                        "step_id": 2,
                        "tool": "email.send",
                        "decision": "confirm",
                        "risk_score": 60,
                        "executed": False,
                        "blocked": False,
                        "requires_confirmation": True,
                        "input_from_steps": [1],
                        "input_labels": ["tainted"],
                    },
                ],
                "security_graph": {
                    "summary": {
                        "node_count": 3,
                        "edge_count": 1,
                        "high_risk_flow_count": 1,
                        "sink_count": 1,
                        "tainted_step_count": 2,
                        "sensitive_step_count": 0
                    },
                    "nodes": [
                        {"id": "case:visual_graph_case", "type": "case", "label": "visual_graph_case", "risk": "medium"},
                        {"id": "step:1", "type": "step", "step_id": 1, "tool": "file.read", "label": "Step 1: file.read", "risk": "low"},
                        {"id": "step:2", "type": "step", "step_id": 2, "tool": "email.send", "label": "Step 2: email.send", "risk": "high"},
                    ],
                    "edges": [
                        {"source": "step:1", "target": "step:2", "labels": ["tainted"], "risk": "high"}
                    ],
                    "high_risk_flows": [
                        {"source": "step:1", "target": "step:2", "tool": "email.send", "risky_labels": ["tainted"], "decision": "confirm", "risk": "high"}
                    ]
                },
            }
        ],
    }

    (tmp_path / "Result_012.json").write_text(
        json.dumps(attach_integrity_manifest(report), ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(benchmark_routes, "RESULTS_DIR", tmp_path)

    response = client.get("/benchmark/latest/graph/visual_graph_case/view")

    assert response.status_code == 200
    assert "Runtime Security Graph" in response.text
    assert "<svg" in response.text
    assert "email.send" in response.text



def test_latest_benchmark_effectiveness_endpoint(tmp_path, monkeypatch):
    report = {
        "summary": {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "pass_rate": 1.0,
            "by_category": {"attack": 1},
            "passed_by_category": {"attack": 1},
        },
        "effectiveness": {
            "version": "1.0",
            "summary": {
                "total_cases": 1,
                "attack_like_cases": 1,
                "mitigated_attack_like_cases": 1,
                "attack_neutralization_rate": 1.0,
                "normal_availability_rate": 0.0,
                "high_risk_flow_mitigation_rate": 1.0,
                "overall_effectiveness_score": 80.0,
                "prevented_risky_execution_count": 2,
            },
            "cases": [],
        },
        "cases": [
            {
                "id": "effectiveness_case",
                "category": "attack",
                "description": "effectiveness case",
                "passed": True,
                "final_decision": "deny",
                "status": "blocked",
                "steps": [],
            }
        ],
    }

    (tmp_path / "Result_013.json").write_text(
        json.dumps(attach_integrity_manifest(report), ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(benchmark_routes, "RESULTS_DIR", tmp_path)

    latest_response = client.get("/benchmark/latest")
    assert latest_response.status_code == 200
    assert latest_response.json()["summary"]["effectiveness"]["overall_effectiveness_score"] == 80.0

    effectiveness_response = client.get("/benchmark/latest/effectiveness")
    assert effectiveness_response.status_code == 200
    assert effectiveness_response.json()["effectiveness"]["summary"]["attack_neutralization_rate"] == 1.0
