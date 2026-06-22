#!/usr/bin/env python3
"""探测积加 ERP 导出（固化后 smoke）。用法: cd backend && uv run python scripts/probe_erp.py [--headed]"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from buque.config import get_settings
from buque.ingestion.gerpgo_session import GerpgGoSession

settings = get_settings()


def _print_columns(label: str, path: Path) -> None:
    if not path.exists():
        print(f"  [{label}] 文件不存在: {path}")
        return
    df = pd.read_excel(path) if path.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(path)
    print(f"  [{label}] 列名: {list(df.columns)}")
    print(f"  [{label}] 行数: {len(df)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="积加 ERP 导出 smoke")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    if not settings.erp_base_url or not settings.erp_username:
        print("跳过: ERP 未配置")
        sys.exit(0)

    md = date.today()
    out_dir = Path(settings.export_dir) / "probe" / md.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)

    with GerpgGoSession(export_dir=out_dir, headless=not args.headed) as session:
        print("=== 库存 merged ===")
        inv = session.export_inventory_merged(md)
        _print_columns("inventory_merged", inv)
        print("\n=== 订单 ===")
        orders = session.export_orders(md)
        _print_columns("orders", orders)
        print("\n=== TMS ===")
        tms = session.export_tms_inbound(md)
        _print_columns("tms_inbound", tms)

    print(f"\n文件目录: {out_dir}")


if __name__ == "__main__":
    main()
