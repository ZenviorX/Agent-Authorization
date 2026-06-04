import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.attack_chain import AttackChainDetector


OUT_JSON = PROJECT_ROOT / "experiments" / "outputs" / "chain_smoke_result.json"
OUT_MD = PROJECT_ROOT / "experiments" / "reports" / "chain_smoke_report.md"


def main() -> None:
    detector = AttackChainDetector(session_id="ci-chain-smoke")
    result = detector.add_event(
        tool="file.read",
        params={"path": "public/notice.txt"},
        gateway_result={"decision": "allow", "risk_score": 10},
    )

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text("# Chain Smoke Report\n\nCI smoke runner completed.\n", encoding="utf-8")

    print("========== Chain Smoke ==========")
    print(f"JSON result file: {OUT_JSON}")
    print(f"Markdown report file: {OUT_MD}")


if __name__ == "__main__":
    main()
