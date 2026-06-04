import html
import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.gateway.gateway import check_tool_call
from backend.schemas import ToolCallRequest


CASE_DIR = PROJECT_ROOT / "security_cases"
OUT_HTML = PROJECT_ROOT / "tests" / "artifacts" / "ci_experiment_dashboard.html"


def safe(value: Any) -> str:
    return html.escape(str(value))


def percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def load_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for path in sorted(CASE_DIR.glob("gateway_cases*.json")):
        with open(path, "r", encoding="utf-8-sig") as f:
            loaded = json.load(f)
        if not isinstance(loaded, list):
            raise ValueError(f"{path} 顶层必须是列表")
        for item in loaded:
            item["_source_file"] = path.name
            cases.append(item)
    if not cases:
        raise RuntimeError("没有找到 gateway_cases*.json，请检查 security_cases 目录。")
    return cases


def expected_match(case: Dict[str, Any], decision: str) -> bool:
    if "expected_decision" in case:
        return decision == case["expected_decision"]
    if "expected_decision_in" in case:
        return decision in case["expected_decision_in"]
    raise ValueError(f"case {case.get('id')} 缺少 expected_decision 或 expected_decision_in")


def security_label(case: Dict[str, Any]) -> str:
    category = str(case.get("category", "")).lower()
    if category in {"normal", "benign", "safe"}:
        return "normal"
    if category in {"attack", "malicious", "dangerous"}:
        return "risk"
    return "suspicious"


def run_unit_tests() -> Dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "elapsed_ms": (time.perf_counter() - started) * 1000,
        "output": proc.stdout[-12000:],
    }


def run_gateway_eval() -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    cases = load_cases()
    rows: List[Dict[str, Any]] = []
    total_latency = 0.0
    passed = 0
    decision_counter = Counter()
    source_counter = Counter()
    category_counter = Counter()
    category_total = defaultdict(int)
    category_passed = defaultdict(int)
    risk_total = 0
    risk_blocked_or_confirmed = 0
    risk_unsafe_allowed = 0
    normal_total = 0
    normal_denied = 0

    for case in cases:
        request = ToolCallRequest(**case["request"])
        started = time.perf_counter()
        result = check_tool_call(request)
        latency_ms = (time.perf_counter() - started) * 1000
        total_latency += latency_ms

        decision = result.get("decision", "unknown")
        ok = expected_match(case, decision)
        label = security_label(case)
        category = case.get("category", "unknown")
        source_file = case.get("_source_file", "unknown")

        passed += int(ok)
        decision_counter[decision] += 1
        source_counter[source_file] += 1
        category_counter[category] += 1
        category_total[category] += 1
        category_passed[category] += int(ok)

        if label == "risk":
            risk_total += 1
            if decision in {"deny", "confirm"}:
                risk_blocked_or_confirmed += 1
            if decision == "allow":
                risk_unsafe_allowed += 1
        elif label == "normal":
            normal_total += 1
            if decision == "deny":
                normal_denied += 1

        rows.append({
            "id": case.get("id"),
            "source_file": source_file,
            "category": category,
            "label": label,
            "description": case.get("description", ""),
            "expected": case.get("expected_decision", case.get("expected_decision_in")),
            "actual": decision,
            "passed": ok,
            "risk_score": result.get("risk_score", ""),
            "risk_level": result.get("risk_level", ""),
            "latency_ms": round(latency_ms, 3),
            "reason": " | ".join(str(x) for x in result.get("reason", [])),
        })

    total = len(cases)
    summary = {
        "total_cases": total,
        "passed_cases": passed,
        "failed_cases": total - passed,
        "accuracy": passed / total if total else 0.0,
        "avg_latency_ms": total_latency / total if total else 0.0,
        "decision_distribution": dict(decision_counter),
        "source_distribution": dict(source_counter),
        "category_distribution": dict(category_counter),
        "category_accuracy": {
            category: {
                "total": total_count,
                "passed": category_passed[category],
                "accuracy": category_passed[category] / total_count if total_count else 0.0,
            }
            for category, total_count in category_total.items()
        },
        "risk_total": risk_total,
        "risk_block_or_confirm_rate": risk_blocked_or_confirmed / risk_total if risk_total else 0.0,
        "risk_unsafe_allow_rate": risk_unsafe_allowed / risk_total if risk_total else 0.0,
        "normal_total": normal_total,
        "normal_false_deny_rate": normal_denied / normal_total if normal_total else 0.0,
    }
    return summary, rows


def metric_cards(summary: Dict[str, Any], tests: Dict[str, Any]) -> str:
    cards = [
        ("单元测试", "通过" if tests["ok"] else "失败", f"耗时 {tests['elapsed_ms']:.0f} ms"),
        ("总样例数", summary.get("total_cases", 0), "security_cases/gateway_cases*.json"),
        ("通过样例", summary.get("passed_cases", 0), f"失败 {summary.get('failed_cases', 0)} 条"),
        ("总体一致率", percent(float(summary.get("accuracy", 0))), "实际决策与期望决策一致"),
        ("风险阻断/确认率", percent(float(summary.get("risk_block_or_confirm_rate", 0))), "风险样例未被直接放行"),
        ("风险误放行率", percent(float(summary.get("risk_unsafe_allow_rate", 0))), "越低越好"),
        ("正常误拒绝率", percent(float(summary.get("normal_false_deny_rate", 0))), "越低越好"),
        ("平均延迟", f"{float(summary.get('avg_latency_ms', 0)):.3f} ms", "单次网关判断耗时"),
    ]
    return "".join(
        "<div class='card'>"
        f"<div class='card-title'>{safe(title)}</div>"
        f"<div class='card-value'>{safe(value)}</div>"
        f"<div class='card-desc'>{safe(desc)}</div>"
        "</div>"
        for title, value, desc in cards
    )


def render_distribution(title: str, data: Dict[str, Any]) -> str:
    if not data:
        return ""
    max_value = max(int(v) for v in data.values()) or 1
    rows = []
    for key, value in sorted(data.items(), key=lambda x: str(x[0])):
        width = int(int(value) / max_value * 100)
        rows.append(
            "<div class='bar-row'>"
            f"<div class='bar-label'>{safe(key)}</div>"
            "<div class='bar-wrap'>"
            f"<div class='bar' style='width:{width}%'></div>"
            "</div>"
            f"<div class='bar-value'>{safe(value)}</div>"
            "</div>"
        )
    return f"<section><h2>{safe(title)}</h2>{''.join(rows)}</section>"


def render_case_table(rows: List[Dict[str, Any]]) -> str:
    sorted_rows = sorted(rows, key=lambda row: (row["passed"], str(row["id"])))
    body = []
    for row in sorted_rows[:120]:
        badge = "ok" if row["passed"] else "bad"
        body.append(
            "<tr>"
            f"<td>{safe(row['id'])}</td>"
            f"<td>{safe(row['source_file'])}</td>"
            f"<td>{safe(row['category'])}</td>"
            f"<td>{safe(row['expected'])}</td>"
            f"<td>{safe(row['actual'])}</td>"
            f"<td><span class='badge {badge}'>{'PASS' if row['passed'] else 'FAIL'}</span></td>"
            f"<td>{safe(row['risk_score'])}</td>"
            f"<td>{safe(row['latency_ms'])} ms</td>"
            f"<td>{safe(row['reason'])}</td>"
            "</tr>"
        )
    return f"""
<section>
  <h2>样例明细</h2>
  <p class="note">失败样例优先显示，最多展示 120 条。</p>
  <table>
    <thead><tr><th>ID</th><th>来源</th><th>分类</th><th>期望</th><th>实际</th><th>结果</th><th>风险分</th><th>延迟</th><th>原因</th></tr></thead>
    <tbody>{''.join(body)}</tbody>
  </table>
</section>
"""


def build_html(summary: Dict[str, Any], rows: List[Dict[str, Any]], tests: Dict[str, Any], error: str = "") -> str:
    sha = os.environ.get("GITHUB_SHA", "local")[:12]
    ref = os.environ.get("GITHUB_REF_NAME", "local")
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    status_class = "pass" if tests.get("ok") and not error and summary.get("failed_cases", 0) == 0 else "fail"
    status_text = "通过" if status_class == "pass" else "需要检查"

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>CI 实验结果仪表盘</title>
  <style>
    body {{ margin: 0; background: #f5f7fb; color: #111827; font-family: Arial, "Microsoft YaHei", sans-serif; }}
    header {{ padding: 34px 46px; background: linear-gradient(135deg, #111827, #1f2937); color: white; }}
    header h1 {{ margin: 0 0 10px; font-size: 30px; }}
    header p {{ margin: 4px 0; color: #d1d5db; }}
    main {{ padding: 28px 46px 56px; }}
    .status {{ display: inline-block; padding: 6px 12px; border-radius: 999px; font-weight: 700; }}
    .status.pass {{ background: #dcfce7; color: #166534; }}
    .status.fail {{ background: #fee2e2; color: #991b1b; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 16px; margin: 24px 0; }}
    .card, section {{ background: white; border: 1px solid #e5e7eb; border-radius: 16px; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06); }}
    .card {{ padding: 18px; }}
    .card-title {{ color: #6b7280; font-size: 14px; }}
    .card-value {{ margin-top: 8px; font-size: 27px; font-weight: 800; }}
    .card-desc {{ margin-top: 6px; color: #9ca3af; font-size: 13px; }}
    section {{ padding: 22px; margin-top: 22px; overflow-x: auto; }}
    section h2 {{ margin: 0 0 14px; font-size: 21px; }}
    .bar-row {{ display: grid; grid-template-columns: 220px 1fr 70px; gap: 12px; align-items: center; margin: 10px 0; }}
    .bar-wrap {{ height: 13px; border-radius: 999px; background: #e5e7eb; overflow: hidden; }}
    .bar {{ height: 100%; background: #2563eb; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 10px; border-bottom: 1px solid #eef2f7; text-align: left; vertical-align: top; }}
    th {{ background: #f3f4f6; color: #374151; }}
    .badge {{ padding: 4px 8px; border-radius: 999px; font-weight: 700; }}
    .badge.ok {{ background: #dcfce7; color: #166534; }}
    .badge.bad {{ background: #fee2e2; color: #991b1b; }}
    pre {{ white-space: pre-wrap; background: #111827; color: #e5e7eb; padding: 16px; border-radius: 12px; max-height: 360px; overflow: auto; }}
    .note {{ color: #6b7280; margin-top: -6px; }}
  </style>
</head>
<body>
  <header>
    <h1>CI 实验结果仪表盘 <span class="status {status_class}">{status_text}</span></h1>
    <p>分支：{safe(ref)}　Commit：{safe(sha)}　Run ID：{safe(run_id)}</p>
    <p>workflow 只负责生成并上传本 HTML；实验失败不会再让 Actions 标红。</p>
  </header>
  <main>
    <div class="cards">{metric_cards(summary, tests)}</div>
    {render_distribution("决策分布", summary.get("decision_distribution", {}))}
    {render_distribution("样例来源分布", summary.get("source_distribution", {}))}
    {render_distribution("分类分布", summary.get("category_distribution", {}))}
    {render_case_table(rows)}
    <section><h2>单元测试输出</h2><pre>{safe(tests.get('output', ''))}</pre></section>
    {f'<section><h2>运行错误</h2><pre>{safe(error)}</pre></section>' if error else ''}
  </main>
</body>
</html>
"""


def main() -> int:
    tests = run_unit_tests()
    error = ""
    summary: Dict[str, Any] = {
        "total_cases": 0,
        "passed_cases": 0,
        "failed_cases": 0,
        "accuracy": 0.0,
        "decision_distribution": {},
        "source_distribution": {},
        "category_distribution": {},
    }
    rows: List[Dict[str, Any]] = []

    try:
        summary, rows = run_gateway_eval()
    except Exception as exc:
        error = repr(exc)

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html(summary, rows, tests, error), encoding="utf-8")
    print(f"HTML dashboard: {OUT_HTML}")

    if error:
        print(f"Dashboard captured runtime error: {error}")
    if not tests["ok"]:
        print("Dashboard captured unit test failures.")
    if summary.get("failed_cases", 0) > 0:
        print(f"Dashboard captured {summary.get('failed_cases')} failed experiment cases.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
