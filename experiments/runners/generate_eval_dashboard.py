import csv
import html
import json
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SUMMARY_JSON = PROJECT_ROOT / "experiments" / "gateway_eval_v2_summary.json"
RESULT_CSV = PROJECT_ROOT / "experiments" / "gateway_eval_v2_results.csv"
OUT_HTML = PROJECT_ROOT / "experiments" / "gateway_eval_dashboard.html"


def percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def safe(value: Any) -> str:
    return html.escape(str(value))


def load_summary() -> Dict[str, Any]:
    if not SUMMARY_JSON.exists():
        raise FileNotFoundError(
            f"未找到 {SUMMARY_JSON}，请先运行 python experiments\\run_gateway_eval_v2.py"
        )

    with open(SUMMARY_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def load_rows() -> List[Dict[str, str]]:
    if not RESULT_CSV.exists():
        raise FileNotFoundError(
            f"未找到 {RESULT_CSV}，请先运行 python experiments\\run_gateway_eval_v2.py"
        )

    with open(RESULT_CSV, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def render_card(title: str, value: str, desc: str = "") -> str:
    return f"""
    <div class="card">
      <div class="card-title">{safe(title)}</div>
      <div class="card-value">{safe(value)}</div>
      <div class="card-desc">{safe(desc)}</div>
    </div>
    """


def render_distribution(title: str, data: Dict[str, Any]) -> str:
    if not data:
        return f"<section><h2>{safe(title)}</h2><p>暂无数据</p></section>"

    max_value = max(int(v) for v in data.values()) or 1
    items = []

    for key, value in sorted(data.items(), key=lambda x: str(x[0])):
        width = int(int(value) / max_value * 100)
        items.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{safe(key)}</div>
              <div class="bar-wrap">
                <div class="bar" style="width:{width}%"></div>
              </div>
              <div class="bar-value">{safe(value)}</div>
            </div>
            """
        )

    return f"""
    <section>
      <h2>{safe(title)}</h2>
      <div class="bar-box">
        {''.join(items)}
      </div>
    </section>
    """


def render_category_accuracy(data: Dict[str, Any]) -> str:
    if not data:
        return "<section><h2>分类准确率</h2><p>暂无数据</p></section>"

    rows = []

    for category, item in sorted(data.items(), key=lambda x: str(x[0])):
        accuracy = float(item.get("accuracy", 0))
        width = int(accuracy * 100)
        rows.append(
            f"""
            <tr>
              <td>{safe(category)}</td>
              <td>{safe(item.get("passed", 0))}/{safe(item.get("total", 0))}</td>
              <td>
                <div class="acc-wrap">
                  <div class="acc-bar" style="width:{width}%"></div>
                </div>
              </td>
              <td>{percent(accuracy)}</td>
            </tr>
            """
        )

    return f"""
    <section>
      <h2>分类准确率</h2>
      <table>
        <thead>
          <tr>
            <th>分类</th>
            <th>通过情况</th>
            <th>可视化</th>
            <th>准确率</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </section>
    """


def render_failed_cases(summary: Dict[str, Any]) -> str:
    failed_cases = summary.get("failed_cases", [])

    if not failed_cases:
        return """
        <section>
          <h2>失败样例</h2>
          <div class="success-box">当前评测无失败样例。</div>
        </section>
        """

    rows = []
    for item in failed_cases:
        rows.append(
            f"""
            <tr>
              <td>{safe(item.get("id", ""))}</td>
              <td>{safe(item.get("source_file", ""))}</td>
              <td>{safe(item.get("category", ""))}</td>
              <td>{safe(item.get("expected", ""))}</td>
              <td>{safe(item.get("actual", ""))}</td>
              <td>{safe(item.get("risk_score", ""))}</td>
              <td>{safe(item.get("reason", ""))}</td>
            </tr>
            """
        )

    return f"""
    <section>
      <h2>失败样例</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>来源文件</th>
            <th>分类</th>
            <th>期望结果</th>
            <th>实际结果</th>
            <th>风险分数</th>
            <th>原因</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </section>
    """


def render_sample_table(rows: List[Dict[str, str]], limit: int = 20) -> str:
    if not rows:
        return "<section><h2>样例明细</h2><p>暂无数据</p></section>"

    selected = rows[:limit]
    body = []

    for row in selected:
        passed = row.get("passed", "")
        badge_class = "badge-ok" if str(passed).lower() == "true" else "badge-bad"

        body.append(
            f"""
            <tr>
              <td>{safe(row.get("id", ""))}</td>
              <td>{safe(row.get("source_file", ""))}</td>
              <td>{safe(row.get("category", ""))}</td>
              <td>{safe(row.get("actual", ""))}</td>
              <td><span class="{badge_class}">{safe(passed)}</span></td>
              <td>{safe(row.get("risk_score", ""))}</td>
              <td>{safe(row.get("risk_level", ""))}</td>
              <td>{safe(row.get("latency_ms", ""))} ms</td>
            </tr>
            """
        )

    return f"""
    <section>
      <h2>样例明细预览</h2>
      <p class="section-note">这里只展示前 {limit} 条，完整结果请查看 gateway_eval_v2_results.csv。</p>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>来源文件</th>
            <th>分类</th>
            <th>决策</th>
            <th>是否通过</th>
            <th>风险分数</th>
            <th>风险等级</th>
            <th>延迟</th>
          </tr>
        </thead>
        <tbody>
          {''.join(body)}
        </tbody>
      </table>
    </section>
    """


def build_html(summary: Dict[str, Any], rows: List[Dict[str, str]]) -> str:
    total_cases = summary.get("total_cases", 0)
    passed_cases = summary.get("passed_cases", 0)
    accuracy = float(summary.get("accuracy", 0))
    avg_latency = float(summary.get("avg_latency_ms", 0))
    attack_rate = float(summary.get("attack_block_or_confirm_rate", 0))
    unsafe_allow_rate = float(summary.get("attack_unsafe_allow_rate", 0))
    false_deny_rate = float(summary.get("normal_false_deny_rate", 0))

    cards = [
        render_card("总样例数", str(total_cases), "自动加载 gateway_cases*.json"),
        render_card("通过样例数", str(passed_cases), "符合期望决策的样例数量"),
        render_card("总体一致率", percent(accuracy), "评测结果与预期标签的一致程度"),
        render_card("平均检测延迟", f"{avg_latency:.3f} ms", "单次工具调用安全检查耗时"),
        render_card("攻击阻断/确认率", percent(attack_rate), "攻击样例被拒绝或升级人工确认"),
        render_card("攻击误放行率", percent(unsafe_allow_rate), "攻击样例被直接允许的比例"),
        render_card("正常任务误拒绝率", percent(false_deny_rate), "正常任务被拒绝的比例"),
    ]

    html_doc = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>Agent Authorization Gateway 安全评测仪表盘</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      font-family: "Microsoft YaHei", Arial, sans-serif;
      background: #f5f7fb;
      color: #1f2937;
    }}

    header {{
      background: linear-gradient(135deg, #111827, #1f2937);
      color: white;
      padding: 36px 52px;
    }}

    header h1 {{
      margin: 0;
      font-size: 30px;
      letter-spacing: 0.5px;
    }}

    header p {{
      margin: 12px 0 0;
      color: #d1d5db;
      font-size: 15px;
    }}

    main {{
      padding: 32px 52px 60px;
    }}

    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 18px;
      margin-bottom: 32px;
    }}

    .card {{
      background: white;
      border-radius: 16px;
      padding: 22px;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
      border: 1px solid #e5e7eb;
    }}

    .card-title {{
      color: #6b7280;
      font-size: 14px;
      margin-bottom: 10px;
    }}

    .card-value {{
      font-size: 30px;
      font-weight: 700;
      color: #111827;
      margin-bottom: 8px;
    }}

    .card-desc {{
      font-size: 13px;
      color: #9ca3af;
      line-height: 1.5;
    }}

    section {{
      background: white;
      border-radius: 16px;
      padding: 24px;
      margin-bottom: 26px;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
      border: 1px solid #e5e7eb;
    }}

    section h2 {{
      margin: 0 0 18px;
      font-size: 21px;
      color: #111827;
    }}

    .section-note {{
      color: #6b7280;
      margin-top: -8px;
      margin-bottom: 16px;
      font-size: 14px;
    }}

    .bar-row {{
      display: grid;
      grid-template-columns: 210px 1fr 60px;
      gap: 12px;
      align-items: center;
      margin: 12px 0;
    }}

    .bar-label {{
      font-size: 14px;
      color: #374151;
      overflow-wrap: anywhere;
    }}

    .bar-wrap, .acc-wrap {{
      height: 13px;
      background: #e5e7eb;
      border-radius: 999px;
      overflow: hidden;
    }}

    .bar {{
      height: 100%;
      background: #2563eb;
      border-radius: 999px;
    }}

    .acc-bar {{
      height: 100%;
      background: #059669;
      border-radius: 999px;
    }}

    .bar-value {{
      font-size: 14px;
      color: #374151;
      text-align: right;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
      overflow: hidden;
    }}

    th {{
      background: #f3f4f6;
      color: #374151;
      text-align: left;
      padding: 12px;
      border-bottom: 1px solid #e5e7eb;
    }}

    td {{
      padding: 12px;
      border-bottom: 1px solid #eef2f7;
      color: #374151;
      vertical-align: top;
    }}

    tr:hover td {{
      background: #f9fafb;
    }}

    .success-box {{
      padding: 18px;
      background: #ecfdf5;
      color: #047857;
      border: 1px solid #a7f3d0;
      border-radius: 12px;
      font-weight: 600;
    }}

    .badge-ok {{
      display: inline-block;
      padding: 4px 9px;
      border-radius: 999px;
      background: #dcfce7;
      color: #166534;
      font-weight: 600;
    }}

    .badge-bad {{
      display: inline-block;
      padding: 4px 9px;
      border-radius: 999px;
      background: #fee2e2;
      color: #991b1b;
      font-weight: 600;
    }}

    footer {{
      padding: 24px 52px;
      color: #6b7280;
      font-size: 13px;
      text-align: center;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Agent Authorization Gateway 安全评测仪表盘</h1>
    <p>面向 AI Agent 工具调用的授权、风险识别、人工确认与攻击拦截评测结果展示</p>
  </header>

  <main>
    <div class="cards">
      {''.join(cards)}
    </div>

    {render_distribution("样例文件分布", summary.get("source_file_distribution", {}))}
    {render_distribution("决策分布", summary.get("decision_distribution", {}))}
    {render_distribution("安全标签分布", summary.get("security_label_distribution", {}))}
    {render_distribution("场景分类分布", summary.get("category_distribution", {}))}
    {render_category_accuracy(summary.get("category_accuracy", {}))}
    {render_failed_cases(summary)}
    {render_sample_table(rows)}
  </main>

  <footer>
    Generated by experiments/generate_eval_dashboard.py
  </footer>
</body>
</html>
"""
    return html_doc


def main() -> None:
    summary = load_summary()
    rows = load_rows()

    html_doc = build_html(summary, rows)

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_doc)

    print("========== Eval Dashboard Generated ==========")
    print(f"HTML: {OUT_HTML}")


if __name__ == "__main__":
    main()
