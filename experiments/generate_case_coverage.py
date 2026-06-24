import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASE_DIR = ROOT / "security_cases"
RESULT_DIR = ROOT / "Results"

def load_cases():
    cases = []
    for path in sorted(CASE_DIR.glob("gateway_cases*.json")):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict) and "cases" in data:
            data = data["cases"]
        if not isinstance(data, list):
            continue
        for case in data:
            if isinstance(case, dict) and "request" in case:
                item = dict(case)
                item["_source_file"] = path.name
                cases.append(item)
    return cases

def expected(case):
    if "expected_decision" in case:
        return [case["expected_decision"]]
    if "expected_decision_in" in case:
        return list(case["expected_decision_in"])
    return []

def is_normal(case):
    category = str(case.get("category", "")).lower()
    case_id = str(case.get("id", "")).lower()
    if category.startswith("normal") or "normal" in case_id:
        return True
    e = set(expected(case))
    return bool(e) and e.issubset({"allow", "confirm"})

def main():
    cases = load_cases()
    RESULT_DIR.mkdir(exist_ok=True)

    by_file = Counter(case["_source_file"] for case in cases)
    by_category = Counter(str(case.get("category", "unknown")) for case in cases)
    by_tool = Counter(str(case.get("request", {}).get("tool", "unknown")) for case in cases)
    by_expected = Counter("/".join(expected(case)) or "missing" for case in cases)

    summary = {
        "total_cases": len(cases),
        "normal_cases": sum(1 for case in cases if is_normal(case)),
        "risk_cases": sum(1 for case in cases if not is_normal(case)),
        "source_files": dict(sorted(by_file.items())),
        "categories": dict(sorted(by_category.items())),
        "tools": dict(sorted(by_tool.items())),
        "expected_decisions": dict(sorted(by_expected.items())),
    }

    (RESULT_DIR / "case_coverage_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Security Case Coverage Report",
        "",
        f"- Total cases: {summary['total_cases']}",
        f"- Normal cases: {summary['normal_cases']}",
        f"- Risk cases: {summary['risk_cases']}",
        "",
        "## By Category",
        "",
        "| Category | Cases |",
        "|---|---:|",
    ]

    for category, count in summary["categories"].items():
        lines.append(f"| {category} | {count} |")

    lines += [
        "",
        "## By Tool",
        "",
        "| Tool | Cases |",
        "|---|---:|",
    ]

    for tool, count in summary["tools"].items():
        lines.append(f"| {tool} | {count} |")

    lines += [
        "",
        "## By Source File",
        "",
        "| Source file | Cases |",
        "|---|---:|",
    ]

    for source, count in summary["source_files"].items():
        lines.append(f"| {source} | {count} |")

    (RESULT_DIR / "case_coverage_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Security Case Coverage</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 32px; background: #f7f8fa; }}
.card {{ background: white; padding: 20px; margin: 12px 0; border-radius: 12px; }}
table {{ width: 100%; border-collapse: collapse; background: white; }}
td, th {{ padding: 8px; border-bottom: 1px solid #eee; text-align: left; }}
</style>
</head>
<body>
<h1>Security Case Coverage</h1>
<div class="card">Total cases: <b>{summary['total_cases']}</b></div>
<div class="card">Normal cases: <b>{summary['normal_cases']}</b></div>
<div class="card">Risk cases: <b>{summary['risk_cases']}</b></div>
<h2>Categories</h2>
<table>
<tr><th>Category</th><th>Cases</th></tr>
{''.join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k, v in summary['categories'].items())}
</table>
</body>
</html>
"""
    (RESULT_DIR / "case_coverage_dashboard.html").write_text(html, encoding="utf-8")

    print("=== Case Coverage Report Finished ===")
    print("total_cases:", summary["total_cases"])
    print("normal_cases:", summary["normal_cases"])
    print("risk_cases:", summary["risk_cases"])

if __name__ == "__main__":
    main()
