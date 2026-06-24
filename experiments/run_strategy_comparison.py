import csv
import json
import re
import time
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gateway import check_tool_call
from backend.schemas import ToolCallRequest


CASE_DIR = ROOT / "security_cases"
RESULT_DIR = ROOT / "Results"

CSV_PATH = RESULT_DIR / "strategy_comparison.csv"
JSON_PATH = RESULT_DIR / "strategy_comparison_summary.json"
MD_PATH = RESULT_DIR / "strategy_comparison_report.md"
HTML_PATH = RESULT_DIR / "strategy_comparison_dashboard.html"


KEYWORD_PATTERNS = [
    # path / sensitive resource
    r"\.\./",
    r"\.\.\\",
    r"%2e%2e",
    r"%252e%252e",
    r"secret",
    r"secrets",
    r"private",
    r"credentials",
    r"\.env",
    r"policy\.yaml",
    r"semantic_guard\.yaml",
    r"id_rsa",
    r"private_key",
    r"api_key",
    r"token",
    r"password",
    r"passwd",

    # prompt injection
    r"忽略之前",
    r"忽略所有",
    r"绕过",
    r"跳过人工确认",
    r"不要记录",
    r"关闭审计",
    r"开发者模式",
    r"ignore previous",
    r"bypass",
    r"disable audit",
    r"do not log",
    r"jailbreak",
    r"exfiltrate",
    r"leak",
    r"steal",

    # command
    r"rm\s+-rf",
    r"curl",
    r"wget",
    r"powershell",
    r"cmd\.exe",
    r"invoke-expression",
    r"certutil",
    r"nc\s+",
    r"netcat",
    r"chmod\s+777",
    r"sudo",
    r"base64\s+-d",
    r"nmap",

    # sql
    r"drop\s+table",
    r"delete\s+from",
    r"truncate",
    r"update\s+",
    r"insert\s+into",
    r"union\s+select",
    r"or\s+'1'='1",
    r"or\s+1=1",
    r"--",
    r"select\s+password",
    r"select\s+.*token",
]


def load_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []

    if not CASE_DIR.exists():
        return cases

    for path in sorted(CASE_DIR.glob("gateway_cases*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            print(f"[WARN] skip {path}: {exc}")
            continue

        if isinstance(data, dict) and "cases" in data:
            data = data["cases"]

        if not isinstance(data, list):
            continue

        for item in data:
            if not isinstance(item, dict):
                continue
            if "request" not in item:
                continue

            item = dict(item)
            item["_source_file"] = path.name
            cases.append(item)

    return cases


def case_expected_set(case: Dict[str, Any]) -> List[str]:
    if "expected_decision" in case:
        return [case["expected_decision"]]
    if "expected_decision_in" in case:
        return list(case["expected_decision_in"])
    return []


def is_normal_case(case: Dict[str, Any]) -> bool:
    category = str(case.get("category", "")).lower()
    case_id = str(case.get("id", "")).lower()

    if category.startswith("normal"):
        return True
    if "normal" in case_id:
        return True

    expected = set(case_expected_set(case))
    if expected and expected.issubset({"allow", "confirm"}):
        return True

    return False


def serialize_request(request: Dict[str, Any]) -> str:
    return json.dumps(request, ensure_ascii=False, sort_keys=True).lower()


def simulate_allow_all(case: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "decision": "allow",
        "risk_score": 0,
        "reason": ["baseline: allow_all permits every tool call"],
    }


def simulate_keyword_only(case: Dict[str, Any]) -> Dict[str, Any]:
    request = case.get("request", {})
    text = serialize_request(request)

    matched = []
    for pattern in KEYWORD_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            matched.append(pattern)

    tool = str(request.get("tool", "")).lower()

    if matched:
        decision = "deny"
        risk_score = min(100, 30 + 10 * len(matched))
        reason = [f"keyword_only matched: {', '.join(matched[:8])}"]
    elif tool in {"file.write", "file.delete", "email.send", "shell.run"}:
        decision = "confirm"
        risk_score = 45
        reason = ["keyword_only found a side-effect tool and requires confirmation"]
    else:
        decision = "allow"
        risk_score = 5
        reason = ["keyword_only found no explicit dangerous keyword"]

    return {
        "decision": decision,
        "risk_score": risk_score,
        "reason": reason,
    }


def simulate_gateway(case: Dict[str, Any]) -> Dict[str, Any]:
    request = ToolCallRequest(**case["request"])
    result = check_tool_call(request)

    if isinstance(result, dict):
        return result

    return {
        "decision": getattr(result, "decision", None),
        "risk_score": getattr(result, "risk_score", 0),
        "reason": getattr(result, "reason", []),
    }


def evaluate_strategy(name: str, case: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    decision = result.get("decision")
    expected = case_expected_set(case)
    normal = is_normal_case(case)

    if expected:
        decision_match = decision in expected
    else:
        decision_match = None

    if normal:
        security_success = decision != "deny"
    else:
        security_success = decision != "allow"

    return {
        "case_id": case.get("id", ""),
        "source_file": case.get("_source_file", ""),
        "category": case.get("category", ""),
        "is_normal": normal,
        "strategy": name,
        "decision": decision,
        "risk_score": result.get("risk_score", 0),
        "expected": "/".join(expected),
        "decision_match": decision_match,
        "security_success": security_success,
        "reason": " | ".join(str(x) for x in result.get("reason", [])[:5]),
    }


def pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}

    for strategy in sorted({row["strategy"] for row in rows}):
        part = [row for row in rows if row["strategy"] == strategy]
        attack = [row for row in part if not row["is_normal"]]
        normal = [row for row in part if row["is_normal"]]
        comparable = [row for row in part if row["decision_match"] is not None]

        attack_total = len(attack)
        normal_total = len(normal)

        attack_block_or_confirm = sum(1 for row in attack if row["decision"] in {"confirm", "deny"})
        attack_allow = sum(1 for row in attack if row["decision"] == "allow")
        normal_not_denied = sum(1 for row in normal if row["decision"] != "deny")
        normal_denied = sum(1 for row in normal if row["decision"] == "deny")
        decision_match = sum(1 for row in comparable if row["decision_match"] is True)

        summary[strategy] = {
            "total_cases": len(part),
            "attack_cases": attack_total,
            "normal_cases": normal_total,
            "attack_block_or_confirm": attack_block_or_confirm,
            "attack_allow": attack_allow,
            "normal_not_denied": normal_not_denied,
            "normal_denied": normal_denied,
            "decision_match_cases": decision_match,
            "comparable_cases": len(comparable),
            "attack_block_or_confirm_rate": attack_block_or_confirm / attack_total if attack_total else 0,
            "attack_allow_rate": attack_allow / attack_total if attack_total else 0,
            "normal_not_denied_rate": normal_not_denied / normal_total if normal_total else 0,
            "normal_denied_rate": normal_denied / normal_total if normal_total else 0,
            "decision_match_rate": decision_match / len(comparable) if comparable else 0,
        }

    return summary


def write_csv(rows: List[Dict[str, Any]]) -> None:
    fieldnames = [
        "case_id",
        "source_file",
        "category",
        "is_normal",
        "strategy",
        "decision",
        "risk_score",
        "expected",
        "decision_match",
        "security_success",
        "reason",
    ]

    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(cases: List[Dict[str, Any]], rows: List[Dict[str, Any]], summary: Dict[str, Any], elapsed_ms: float) -> None:
    lines = []
    lines.append("# 多策略对比评测报告")
    lines.append("")
    lines.append("## 1. 实验目的")
    lines.append("")
    lines.append("本实验在同一批安全样例上对比三种工具调用控制策略：")
    lines.append("")
    lines.append("- `allow_all`：无前置安全控制，所有工具调用直接放行；")
    lines.append("- `keyword_only`：仅依赖显式关键词和副作用工具进行判断；")
    lines.append("- `gateway`：使用本项目完整 Gateway 进行工具、资源、角色、置信度和策略综合判断。")
    lines.append("")
    lines.append("该实验用于评估完整 Gateway 相比基础策略在攻击阻断、风险升级和正常任务保留方面的差异。")
    lines.append("")
    lines.append("## 2. 实验规模")
    lines.append("")
    lines.append(f"- 样例总数：{len(cases)}")
    lines.append(f"- 记录总数：{len(rows)}")
    lines.append(f"- 总耗时：{elapsed_ms:.2f} ms")
    lines.append("")
    lines.append("## 3. 核心结果")
    lines.append("")
    lines.append("| 策略 | 总样例 | 攻击样例 | 正常样例 | 攻击阻断/确认率 | 攻击误放行率 | 正常不误拒率 | 决策匹配率 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")

    for strategy in ["allow_all", "keyword_only", "gateway"]:
        item = summary.get(strategy)
        if not item:
            continue

        lines.append(
            "| {strategy} | {total} | {attack} | {normal} | {attack_rate} | {attack_allow} | {normal_rate} | {match_rate} |".format(
                strategy=strategy,
                total=item["total_cases"],
                attack=item["attack_cases"],
                normal=item["normal_cases"],
                attack_rate=pct(item["attack_block_or_confirm_rate"]),
                attack_allow=pct(item["attack_allow_rate"]),
                normal_rate=pct(item["normal_not_denied_rate"]),
                match_rate=pct(item["decision_match_rate"]),
            )
        )

    lines.append("")
    lines.append("## 4. 结果解释")
    lines.append("")
    lines.append("`allow_all` 代表缺少前置安全边界的模式。它通常不会拒绝正常任务，但攻击样例也会被直接放行。")
    lines.append("")
    lines.append("`keyword_only` 可以拦截包含明显危险词的请求，但缺少角色权限、资源风险、任务置信度和上下文约束，面对复杂工具调用时解释能力有限。")
    lines.append("")
    lines.append("`gateway` 是本项目完整方案。它综合工具类型、资源路径、用户角色、Agent 置信度、任务合约和策略阈值，将工具调用分为 allow、confirm、deny 三类结果。")
    lines.append("")
    lines.append("## 5. 输出文件")
    lines.append("")
    lines.append(f"- CSV 明细：`{CSV_PATH.as_posix()}`")
    lines.append(f"- JSON 摘要：`{JSON_PATH.as_posix()}`")
    lines.append(f"- HTML 仪表盘：`{HTML_PATH.as_posix()}`")

    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def html_escape(text: Any) -> str:
    s = str(text)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_html(summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
    cards = []

    for strategy in ["allow_all", "keyword_only", "gateway"]:
        item = summary.get(strategy)
        if not item:
            continue

        cards.append(f"""
        <div class="card">
          <h2>{strategy}</h2>
          <p class="metric">{pct(item["attack_block_or_confirm_rate"])}</p>
          <p>攻击阻断/确认率</p>
          <p>攻击误放行率：<b>{pct(item["attack_allow_rate"])}</b></p>
          <p>正常不误拒率：<b>{pct(item["normal_not_denied_rate"])}</b></p>
          <p>决策匹配率：<b>{pct(item["decision_match_rate"])}</b></p>
        </div>
        """)

    detail_rows = []
    for row in rows[:300]:
        detail_rows.append(
            "<tr>"
            f"<td>{html_escape(row['case_id'])}</td>"
            f"<td>{html_escape(row['category'])}</td>"
            f"<td>{html_escape(row['strategy'])}</td>"
            f"<td>{html_escape(row['decision'])}</td>"
            f"<td>{html_escape(row['expected'])}</td>"
            f"<td>{html_escape(row['decision_match'])}</td>"
            f"<td>{html_escape(row['reason'])}</td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>Agent-Authorization 多策略对比评测</title>
<style>
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
  margin: 32px;
  background: #f7f8fa;
  color: #222;
}}
h1 {{ margin-bottom: 8px; }}
.subtitle {{ color: #555; margin-bottom: 24px; }}
.cards {{
  display: grid;
  grid-template-columns: repeat(3, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}}
.card {{
  background: white;
  border-radius: 14px;
  padding: 20px;
  box-shadow: 0 4px 18px rgba(0,0,0,0.08);
}}
.card h2 {{ margin-top: 0; }}
.metric {{
  font-size: 34px;
  font-weight: 800;
  margin: 8px 0;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 18px rgba(0,0,0,0.06);
}}
th, td {{
  padding: 10px;
  border-bottom: 1px solid #eee;
  text-align: left;
  vertical-align: top;
  font-size: 13px;
}}
th {{
  background: #1f2937;
  color: white;
}}
.note {{
  background: #fff;
  border-left: 5px solid #1f2937;
  padding: 14px 18px;
  margin: 20px 0;
}}
</style>
</head>
<body>
<h1>Agent-Authorization 多策略对比评测</h1>
<p class="subtitle">allow_all / keyword_only / gateway 在同一批安全样例上的评测结果</p>

<div class="cards">
{''.join(cards)}
</div>

<div class="note">
  <b>说明：</b> allow_all 代表无前置控制，keyword_only 代表基础关键词策略，gateway 代表本项目完整安全网关。
  该对比用于评估不同策略在攻击阻断和正常任务保留方面的差异。
</div>

<h2>样例明细</h2>
<table>
<thead>
<tr>
<th>Case ID</th>
<th>Category</th>
<th>Strategy</th>
<th>Decision</th>
<th>Expected</th>
<th>Match</th>
<th>Reason</th>
</tr>
</thead>
<tbody>
{''.join(detail_rows)}
</tbody>
</table>
</body>
</html>
"""

    HTML_PATH.write_text(html, encoding="utf-8")


def main() -> None:
    start = time.perf_counter()

    cases = load_cases()
    if not cases:
        raise SystemExit("No gateway_cases*.json found in security_cases")

    strategies = {
        "allow_all": simulate_allow_all,
        "keyword_only": simulate_keyword_only,
        "gateway": simulate_gateway,
    }

    rows: List[Dict[str, Any]] = []

    for case in cases:
        for name, func in strategies.items():
            try:
                result = func(case)
                row = evaluate_strategy(name, case, result)
            except Exception as exc:
                row = {
                    "case_id": case.get("id", ""),
                    "source_file": case.get("_source_file", ""),
                    "category": case.get("category", ""),
                    "is_normal": is_normal_case(case),
                    "strategy": name,
                    "decision": "error",
                    "risk_score": 0,
                    "expected": "/".join(case_expected_set(case)),
                    "decision_match": False,
                    "security_success": False,
                    "reason": str(exc),
                }

            rows.append(row)

    elapsed_ms = (time.perf_counter() - start) * 1000
    summary = summarize(rows)

    RESULT_DIR.mkdir(exist_ok=True)

    write_csv(rows)

    JSON_PATH.write_text(
        json.dumps(
            {
                "available": True,
                "total_cases": len(cases),
                "total_records": len(rows),
                "elapsed_ms": elapsed_ms,
                "summary": summary,
                "outputs": {
                    "csv": str(CSV_PATH.relative_to(ROOT)),
                    "json": str(JSON_PATH.relative_to(ROOT)),
                    "markdown": str(MD_PATH.relative_to(ROOT)),
                    "html": str(HTML_PATH.relative_to(ROOT)),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    write_markdown(cases, rows, summary, elapsed_ms)
    write_html(summary, rows)

    print("=== Strategy Comparison Finished ===")
    print(f"cases: {len(cases)}")
    print(f"records: {len(rows)}")
    print(f"csv: {CSV_PATH}")
    print(f"json: {JSON_PATH}")
    print(f"markdown: {MD_PATH}")
    print(f"html: {HTML_PATH}")

    for strategy in ["allow_all", "keyword_only", "gateway"]:
        item = summary.get(strategy)
        if not item:
            continue

        print(
            f"{strategy}: "
            f"attack_block_or_confirm={pct(item['attack_block_or_confirm_rate'])}, "
            f"attack_allow={pct(item['attack_allow_rate'])}, "
            f"normal_not_denied={pct(item['normal_not_denied_rate'])}, "
            f"decision_match={pct(item['decision_match_rate'])}"
        )


if __name__ == "__main__":
    main()
