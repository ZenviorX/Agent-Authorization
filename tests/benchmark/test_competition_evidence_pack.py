import json
from pathlib import Path

from backend.evidence.integrity import attach_integrity_manifest
from experiments.generate_competition_evidence_pack import generate_evidence_pack


def test_generate_competition_evidence_pack_outputs_markdown_and_json(tmp_path: Path):
    report = {
        "summary": {
            "generated_at": "2026-06-09T00:00:00+00:00",
            "total": 1,
            "passed": 1,
            "failed": 0,
            "pass_rate": 1.0,
        },
        "effectiveness": {
            "summary": {
                "overall_effectiveness_score": 88.0,
                "attack_neutralization_rate": 1.0,
                "normal_availability_rate": 1.0,
                "prevented_risky_execution_count": 2,
            }
        },
        "cases": [
            {
                "id": "attack_case",
                "category": "attack",
                "description": "attack case",
                "passed": True,
                "final_decision": "confirm",
                "status": "confirm_required",
                "steps": [
                    {
                        "step_id": 1,
                        "tool": "email.send",
                        "decision": "confirm",
                        "executed": False,
                        "input_labels": ["tainted"],
                    }
                ],
                "security_graph": {
                    "summary": {
                        "node_count": 2,
                        "edge_count": 1,
                        "sink_count": 1,
                        "high_risk_flow_count": 1,
                    },
                    "high_risk_flows": [
                        {
                            "source": "step:1",
                            "target": "sink:email.send",
                            "tool": "email.send",
                            "risky_labels": ["tainted"],
                            "decision": "confirm",
                        }
                    ],
                },
            }
        ],
    }

    report_path = tmp_path / "Result_001.json"
    report_path.write_text(
        json.dumps(attach_integrity_manifest(report), ensure_ascii=False),
        encoding="utf-8",
    )

    result = generate_evidence_pack(
        report_path=report_path,
        output_dir=tmp_path,
    )

    md_path = result["markdown_path"]
    json_path = result["json_path"]

    assert md_path.exists()
    assert json_path.exists()

    md_text = md_path.read_text(encoding="utf-8")

    assert "AgentGuard 竞赛证据包" in md_text
    assert "防护覆盖矩阵" in md_text
    assert "AgentGuard vs Naive Baseline" in md_text
    assert "attack_case" in md_text

    pack = json.loads(json_path.read_text(encoding="utf-8"))

    assert pack["executive_summary"]["integrity_valid"] is True
    assert pack["executive_summary"]["coverage_score"] > 0
