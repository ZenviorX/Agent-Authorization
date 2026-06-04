import html
import json
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_JSON = PROJECT_ROOT / "experiments" / "outputs" / "baseline_comparison_summary.json"
OUT_HTML = PROJECT_ROOT / "experiments" / "dashboards" / "baseline_comparison_dashboard.html"


def safe(value: Any) -> str:
    return html.escape(str(value))


def percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def load_summary() -> Dict[str, Any]:
    if not SUMMARY_JSON.exists():
        raise FileNotFoundError(
            f"未找到 {SUMMARY_JSON}，请先运行 python experiments/runners/run_baseline_comparison.py"
        )
    with open(SUMMARY_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def build_html(summary: Dict[str, Any]) -> str:
    rows = []
    for strategy, item in summary.items():
        rows.append(
            "<tr>"
            f"<td>{safe(strategy)}</td>"
            f"<td>{safe(item.get('total_cases', 0))}</td>"
            f"<td>{percent(float(item.get('accuracy', 0)))}</td>"
            f"<td>{percent(float(item.get('attack_block_or_confirm_rate', 0)))}</td>"
            f"<td>{percent(float(item.get('attack_unsafe_allow_rate', 0)))}</td>"
            f"<td>{percent(float(item.get('normal_false_deny_rate', 0)))}</td>"
            f"<td>{float(item.get('avg_latency_ms', 0)):.3f} ms</td>"
            "</tr>"
        )

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>Agent Authorization Gateway 对比实验仪表盘</title>
  <style>
    body {{ margin: 0; padding: 32px; font-family: Arial, "Microsoft YaHei", sans-serif; background: #f5f7fb; color: #111827; }}
    main {{ max-width: 1200px; margin: 0 auto; }}
    h1 {{ margin-bottom: 8px; }}
    p {{ color: #6b7280; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; }}
    th, td {{ padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: left; }}
    th {{ background: #f3f4f6; }}
  </style>
</head>
<body>
  <main>
    <h1>Agent Authorization Gateway 对比实验仪表盘</h1>
    <p>对比无防护基线、关键词规则和安全网关在同一评测集上的表现。</p>
    <table>
      <thead>
        <tr>
          <th>方案</th><th>总样例数</th><th>总体一致率</th><th>攻击阻断/确认率</th><th>攻击误放行率</th><th>正常误拒绝率</th><th>平均延迟</th>
        </tr>
      </thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </main>
</body>
</html>
"""


def main() -> None:
    summary = load_summary()
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html(summary), encoding="utf-8")
    print("========== Baseline Comparison Dashboard Generated ==========")
    print(f"HTML: {OUT_HTML}")


if __name__ == "__main__":
    main()
