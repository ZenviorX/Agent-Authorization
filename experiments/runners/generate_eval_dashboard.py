import csv
import html
import json
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_JSON = PROJECT_ROOT / "experiments" / "outputs" / "gateway_eval_v2_summary.json"
RESULT_CSV = PROJECT_ROOT / "experiments" / "outputs" / "gateway_eval_v2_results.csv"
OUT_HTML = PROJECT_ROOT / "experiments" / "dashboards" / "gateway_eval_dashboard.html"


def percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def safe(value: Any) -> str:
    return html.escape(str(value))


def load_summary() -> Dict[str, Any]:
    if not SUMMARY_JSON.exists():
        raise FileNotFoundError(
            f"未找到 {SUMMARY_JSON}，请先运行 python experiments/runners/run_gateway_eval_v2.py"
        )
    with open(SUMMARY_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def load_rows() -> List[Dict[str, str]]:
    if not RESULT_CSV.exists():
        raise FileNotFoundError(
            f"未找到 {RESULT_CSV}，请先运行 python experiments/runners/run_gateway_eval_v2.py"
        )
    with open(RESULT_CSV, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_html(summary: Dict[str, Any], rows: List[Dict[str, str]]) -> str:
    cards = [
        ("总样例数", summary.get("total_cases", 0)),
        ("通过样例数", summary.get("passed_cases", 0)),
        ("总体一致率", percent(float(summary.get("accuracy", 0)))),
        ("攻击阻断/确认率", percent(float(summary.get("attack_block_or_confirm_rate", 0)))),
        ("攻击误放行率", percent(float(summary.get("attack_unsafe_allow_rate", 0)))),
        ("正常误拒绝率", percent(float(summary.get("normal_false_deny_rate", 0)))),
        ("平均延迟", f"{float(summary.get('avg_latency_ms', 0)):.3f} ms"),
    ]
    card_html = "".join(
        f"<div class='card'><div class='label'>{safe(title)}</div><div class='value'>{safe(value)}</div></div>"
        for title, value in cards
    )

    preview_rows = "".join(
        "<tr>"
        f"<td>{safe(row.get('id', ''))}</td>"
        f"<td>{safe(row.get('source_file', ''))}</td>"
        f"<td>{safe(row.get('category', ''))}</td>"
        f"<td>{safe(row.get('actual', ''))}</td>"
        f"<td>{safe(row.get('passed', ''))}</td>"
        f"<td>{safe(row.get('risk_score', ''))}</td>"
        "</tr>"
        for row in rows[:20]
    )

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>Agent Authorization Gateway 安全评测仪表盘</title>
  <style>
    body {{ margin: 0; padding: 32px; font-family: Arial, "Microsoft YaHei", sans-serif; background: #f5f7fb; color: #111827; }}
    main {{ max-width: 1200px; margin: 0 auto; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin: 24px 0; }}
    .card {{ background: white; border: 1px solid #e5e7eb; border-radius: 14px; padding: 18px; }}
    .label {{ color: #6b7280; font-size: 14px; }}
    .value {{ margin-top: 8px; font-size: 24px; font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; }}
    th, td {{ padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: left; }}
    th {{ background: #f3f4f6; }}
  </style>
</head>
<body>
  <main>
    <h1>Agent Authorization Gateway 安全评测仪表盘</h1>
    <p>自动加载 gateway_cases*.json 后生成的评测摘要。</p>
    <section class="cards">{card_html}</section>
    <h2>样例明细预览</h2>
    <table>
      <thead><tr><th>ID</th><th>来源文件</th><th>分类</th><th>决策</th><th>是否通过</th><th>风险分</th></tr></thead>
      <tbody>{preview_rows}</tbody>
    </table>
  </main>
</body>
</html>
"""


def main() -> None:
    summary = load_summary()
    rows = load_rows()
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html(summary, rows), encoding="utf-8")
    print("========== Gateway Dashboard Generated ==========")
    print(f"HTML: {OUT_HTML}")


if __name__ == "__main__":
    main()
