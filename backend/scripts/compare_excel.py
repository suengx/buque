"""Excel 规则一致率比对脚本。"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def compare(baseline_path: Path, system_path: Path, key_cols: list[str]) -> dict:
    baseline = pd.read_excel(baseline_path) if baseline_path.suffix == ".xlsx" else pd.read_csv(baseline_path)
    system = pd.read_excel(system_path) if system_path.suffix == ".xlsx" else pd.read_csv(system_path)

    merged = baseline.merge(system, on=key_cols, how="inner", suffixes=("_base", "_sys"))
    if merged.empty:
        return {"match_rate": 0.0, "matched": 0, "total": len(baseline), "diff_rows": []}

    level_match = merged["risk_level_base"] == merged["risk_level_sys"]
    match_rate = level_match.mean()
    diffs = merged[~level_match][key_cols + ["risk_level_base", "risk_level_sys"]]
    return {
        "match_rate": float(match_rate),
        "matched": int(level_match.sum()),
        "total": len(merged),
        "diff_rows": diffs.head(20).to_dict(orient="records"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="BuQue Excel 一致率比对")
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--system", required=True, type=Path)
    parser.add_argument("--keys", default="sku,warehouse", help="逗号分隔主键列")
    args = parser.parse_args()
    result = compare(args.baseline, args.system, args.keys.split(","))
    print(f"一致率: {result['match_rate']:.2%} ({result['matched']}/{result['total']})")
    if result["diff_rows"]:
        print("差异样例:")
        for row in result["diff_rows"]:
            print(row)


if __name__ == "__main__":
    main()
