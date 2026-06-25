import csv
import json
from pathlib import Path
from collections import defaultdict


ROOT = Path(__file__).resolve().parent.parent
RESULT_DIR = ROOT / "Results"
CSV_PATH = RESULT_DIR / "strategy_comparison.csv"
JSON_PATH = RESULT_DIR / "strategy_error_analysis.json"
MD_PATH = RESULT_DIR / "strategy_error_analysis.md"


def load_rows():
    if not CSV_PATH.exists():
        raise SystemExit("strategy_comparison.csv not found. Run scripts/run_strategy_comparison.ps1 first.")

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def bool_value(value):
    return str(value).lower() == "true"


def analyze(rows):
    result = {}

    strategies = sorted({row["strategy"] for row in rows})

    for strategy in strategies:
        part = [row for row in rows if row["strategy"] == strategy]

        attack_allow = [
            row for row in part
            if row["is_normal"].lower() == "false" and row["decision"] == "allow"
        ]

        normal_denied = [
            row for row in part
            if row["is_normal"].lower() == "true" and row["decision"] == "deny"
        ]

        mismatches = [
            row for row in part
            if row["decision_match"].lower() == "false"
        ]

        by_category = defaultdict(lambda: {
            "total": 0,
            "attack_allow": 0,
            "normal_denied": 0,
            "mismatch": 0,
        })

        for row in part:
            category = row["category"] or "unknown"
            by_category[category]["total"] += 1

            if row in attack_allow:
                by_category[category]["attack_allow"] += 1

            if row in normal_denied:
                by_category[category]["normal_denied"] += 1

            if row in mismatches:
                by_category[category]["mismatch"] += 1

        result[strategy] = {
            "total": len(part),
            "attack_allow_count": len(attack_allow),
            "normal_denied_count": len(normal_denied),
            "mismatch_count": len(mismatches),
            "attack_allow_cases": [row["case_id"] for row in attack_allow[:30]],
            "normal_denied_cases": [row["case_id"] for row in normal_denied[:30]],
            "mismatch_cases": [row["case_id"] for row in mismatches[:30]],
            "by_category": dict(by_category),
        }

    return result


def write_markdown(analysis):
    lines = []
    lines.append("# ?????????")
    lines.append("")
    lines.append("## 1. ????")
    lines.append("")
    lines.append("????? `Results/strategy_comparison.csv` ?????????????????????????????????????")
    lines.append("")
    lines.append("???????")
    lines.append("")
    lines.append("- ????????????????? allow?")
    lines.append("- ?????????????? deny?")
    lines.append("- ??????????????????????")
    lines.append("")
    lines.append("## 2. ????")
    lines.append("")
    lines.append("| ?? | ??? | ????? | ????? | ????? |")
    lines.append("|---|---:|---:|---:|---:|")

    for strategy, item in analysis.items():
        lines.append(
            f"| {strategy} | {item['total']} | {item['attack_allow_count']} | "
            f"{item['normal_denied_count']} | {item['mismatch_count']} |"
        )

    lines.append("")
    lines.append("## 3. ??????")
    lines.append("")

    for strategy, item in analysis.items():
        lines.append(f"### {strategy}")
        lines.append("")

        if item["attack_allow_cases"]:
            lines.append("????????")
            for case_id in item["attack_allow_cases"]:
                lines.append(f"- `{case_id}`")
        else:
            lines.append("??????????")

        lines.append("")

        if item["normal_denied_cases"]:
            lines.append("????????")
            for case_id in item["normal_denied_cases"]:
                lines.append(f"- `{case_id}`")
        else:
            lines.append("??????????")

        lines.append("")

        if item["mismatch_cases"]:
            lines.append("????????")
            for case_id in item["mismatch_cases"]:
                lines.append(f"- `{case_id}`")
        else:
            lines.append("??????????")

        lines.append("")

    lines.append("## 4. ??")
    lines.append("")
    lines.append("?????????????`allow_all` ?????????????`keyword_only` ????????????????????`gateway` ???????????????????????")

    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    rows = load_rows()
    analysis = analyze(rows)

    JSON_PATH.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    write_markdown(analysis)

    print("=== Strategy Error Analysis Finished ===")
    print(f"json: {JSON_PATH}")
    print(f"markdown: {MD_PATH}")

    for strategy, item in analysis.items():
        print(
            f"{strategy}: attack_allow={item['attack_allow_count']}, "
            f"normal_denied={item['normal_denied_count']}, "
            f"mismatch={item['mismatch_count']}"
        )


if __name__ == "__main__":
    main()
