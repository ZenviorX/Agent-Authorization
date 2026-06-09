from pathlib import Path

from experiments.run_llm_runtime_benchmark import run_benchmark


def test_offline_llm_runtime_benchmark_runs_all_cases_without_real_llm():
    report = run_benchmark(write_reports=False)

    summary = report["summary"]

    assert summary["total"] >= 15
    assert summary["passed"] >= 12
    assert summary["pass_rate"] >= 0.65

    categories = summary["by_category"]
    assert categories.get("normal", 0) >= 4
    assert categories.get("attack", 0) >= 8
    assert categories.get("suspicious", 0) >= 2

    first_case = report["cases"][0]
    assert "security_graph" in first_case
    assert "summary" in first_case["security_graph"]
    assert first_case["security_graph"]["summary"]["node_count"] >= 2
    assert "effectiveness" in report
    assert report["effectiveness"]["summary"]["total_cases"] == summary["total"]
    assert report["effectiveness"]["summary"]["overall_effectiveness_score"] >= 0


def test_offline_llm_runtime_benchmark_writes_reports(tmp_path: Path):
    json_path = tmp_path / "benchmark.json"
    html_path = tmp_path / "benchmark.html"

    report = run_benchmark(
        write_reports=True,
        result_json=json_path,
        result_html=html_path,
    )

    assert json_path.exists()
    assert html_path.exists()

    assert report["summary"]["total"] >= 15
    assert "LLM Runtime Offline Benchmark" in html_path.read_text(encoding="utf-8")
