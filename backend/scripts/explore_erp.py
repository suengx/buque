#!/usr/bin/env python3
"""积加 ERP 结构化探索：截图 + 导出 + report.json + REPORT.md

用法: cd backend && uv run python scripts/explore_erp.py [--headed] [--ingest]
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import pandas as pd
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from buque.config import get_settings
from buque.ingestion import gerpgo_ui
from buque.ingestion.erp_exporter import run_ingestion_from_files
from buque.ingestion.erp_selectors import (
    INVENTORY_P0_COLUMN_ALIASES,
    ORDERS_EXPORT_MENU_ITEM,
    ORDERS_P0_COLUMN_ALIASES,
    PATHS,
    TMS_P0_COLUMN_ALIASES,
    TRANSPORT_TASK_HINTS,
)

settings = get_settings()


def _run_dir() -> Path:
    ts = datetime.now(settings.tz).strftime("%Y-%m-%d_%H%M%S")
    d = Path(__file__).resolve().parents[1] / "data" / "erp_probe" / ts
    (d / "screenshots").mkdir(parents=True, exist_ok=True)
    (d / "exports").mkdir(parents=True, exist_ok=True)
    return d


def _read_file_meta(path: Path) -> tuple[int, list[str]]:
    if not path.exists():
        return 0, []
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    return len(df), [str(c) for c in df.columns]


def _p0_present(columns: list[str], aliases: dict[str, tuple[str, ...]]) -> list[str]:
    colset = {c.strip() for c in columns}
    found: list[str] = []
    for field, names in aliases.items():
        if colset.intersection(names):
            found.append(field)
    return found


def _shot(page: Page, run_dir: Path, name: str) -> str:
    rel = f"screenshots/{name}.png"
    page.screenshot(path=str(run_dir / rel), full_page=False)
    return rel


def _explore_export(
    page: Page,
    run_dir: Path,
    *,
    source: str,
    export_name: str,
    export_fn: Callable[[Page, Path], tuple[str, str, list[str]]],
    p0_aliases: dict[str, tuple[str, ...]],
    shot_prefix: str,
    export_flow: list[str],
) -> dict:
    record: dict = {
        "source": source,
        "status": "FAILED",
        "export_flow": export_flow,
        "screenshots": [],
        "popups_seen": [],
    }
    target = run_dir / "exports" / export_name
    try:
        record["screenshots"].append(_shot(page, run_dir, f"{shot_prefix}_01_before"))
        shell_url, iframe_url, popups = export_fn(page, target)
        record["shell_url"] = shell_url
        record["iframe_url"] = iframe_url
        record["popups_seen"] = popups
        record["file_path"] = f"exports/{export_name}"
        row_count, columns = _read_file_meta(target)
        record["row_count"] = row_count
        record["columns"] = columns
        p0 = _p0_present(columns, p0_aliases)
        record["p0_fields_present"] = p0
        record["p0_fields_required"] = list(p0_aliases.keys())
        if row_count == 0:
            record["status"] = "SUCCESS"
        elif len(p0) >= len(p0_aliases):
            record["status"] = "SUCCESS"
        else:
            record["status"] = "PARTIAL"
        record["screenshots"].append(_shot(page, run_dir, f"{shot_prefix}_02_after_export"))
    except Exception as exc:
        record["error"] = str(exc)
        record["traceback"] = traceback.format_exc()
        try:
            record["screenshots"].append(_shot(page, run_dir, f"{shot_prefix}_error"))
        except Exception:
            pass
    return record


def _overall(sources: list[dict]) -> str:
    statuses = [s["status"] for s in sources]
    if all(s == "SUCCESS" for s in statuses):
        return "COMPLETE"
    if any(s in ("SUCCESS", "PARTIAL") for s in statuses):
        return "PARTIAL"
    return "FAILED"


def _write_report_md(run_dir: Path, report: dict) -> None:
    lines = [
        "# ERP Playwright 探索交付报告",
        "",
        f"- 运行时间: {report['run_at']}",
        f"- ERP Base: {report['erp_base']}",
        f"- 整体结论: **{report['overall']}**",
        "",
        "## A. 采集汇总",
        "",
        "| 源 | 状态 | 行数 | P0字段 | 壳 URL | iframe URL | 导出文件 |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in report["sources"]:
        if s["source"] not in ("erp_inventory", "erp_orders", "tms_inbound"):
            continue
        p0 = f"{len(s.get('p0_fields_present', []))}/{len(s.get('p0_fields_required', []))}"
        lines.append(
            f"| {s['source']} | {s['status']} | {s.get('row_count', '-')} | {p0} | "
            f"{s.get('shell_url', '-')} | {s.get('iframe_url', '-')} | {s.get('file_path', '-')} |"
        )
    lines.extend(["", "## B. 每源截图证据", ""])
    for key in ("erp_inventory", "erp_orders", "tms_inbound"):
        s = next((x for x in report["sources"] if x["source"] == key), None)
        if not s:
            continue
        lines.append(f"### {s['source']}")
        lines.append(f"- 状态: {s['status']}")
        if s.get("error"):
            lines.append(f"- 错误: `{s['error']}`")
        lines.append(f"- 弹窗处理: {', '.join(s.get('popups_seen', [])) or '无'}")
        for sh in s.get("screenshots", []):
            lines.append(f"- ![{sh}]({sh})")
        lines.append("")
    lines.extend(
        [
            "## C. 路径 SSOT",
            "",
            "见 `backend/src/buque/ingestion/erp_selectors.py`",
            "",
            "## D. 已知风险",
            "",
            "- 验证码出现时需 `--headed` 人工处理",
            "- 订单导出经传输中心异步，处理时间可达数分钟",
            "- TMS 无 bulk 导出，采用详情页「产品收发货明细」抓取",
            "- TMS 无在途时 0 行仍可为 SUCCESS",
            "",
        ]
    )
    (run_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--ingest", action="store_true", help="导出后写入数据库")
    args = parser.parse_args()

    if not settings.erp_base_url or not settings.erp_username:
        print("请配置 ERP_BASE_URL / ERP_USERNAME / ERP_PASSWORD")
        sys.exit(1)

    run_dir = _run_dir()
    md = date.today()
    sources: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        page = browser.new_context(accept_downloads=True, viewport={"width": 1920, "height": 1080}).new_page()
        gerpgo_ui.login(page)
        _shot(page, run_dir, "00_login")

        inv_product = _explore_export(
            page,
            run_dir,
            source="erp_inventory",
            export_name="inventory_product.xlsx",
            export_fn=gerpgo_ui.export_inventory_product,
            p0_aliases=INVENTORY_P0_COLUMN_ALIASES,
            shot_prefix="inventory_product",
            export_flow=[
                "login",
                "goto_shell",
                "app_frame",
                "dismiss_modals",
                "import_export_menu",
                "export_button",
                f"transport_center:{TRANSPORT_TASK_HINTS.inventory}",
            ],
        )
        sources.append(inv_product)

        inv_multi = _explore_export(
            page,
            run_dir,
            source="erp_inventory_multi",
            export_name="inventory_multi_platform.xlsx",
            export_fn=gerpgo_ui.export_inventory_multi_platform,
            p0_aliases=INVENTORY_P0_COLUMN_ALIASES,
            shot_prefix="inventory_multi",
            export_flow=[
                "login",
                "goto_shell",
                "app_frame",
                "dismiss_modals",
                "direct_export_button",
                f"transport_center:{TRANSPORT_TASK_HINTS.inventory}",
            ],
        )
        sources.append(inv_multi)

        merge_path = run_dir / "exports" / "inventory_merged.xlsx"
        frames: list[pd.DataFrame] = []
        for name in ("inventory_product.xlsx", "inventory_multi_platform.xlsx"):
            fp = run_dir / "exports" / name
            if fp.exists():
                frames.append(pd.read_excel(fp))
        if frames:
            merged = pd.concat(frames, ignore_index=True)
            dedupe_cols = [c for c in ("SKU", "仓库") if c in merged.columns]
            if dedupe_cols:
                merged = merged.drop_duplicates(subset=dedupe_cols, keep="last")
            merged.to_excel(merge_path, index=False)
            inv_product["merged_file"] = "exports/inventory_merged.xlsx"
            inv_product["merged_row_count"] = len(pd.read_excel(merge_path))

        orders = _explore_export(
            page,
            run_dir,
            source="erp_orders",
            export_name="orders.xlsx",
            export_fn=gerpgo_ui.export_orders,
            p0_aliases=ORDERS_P0_COLUMN_ALIASES,
            shot_prefix="orders",
            export_flow=[
                "login",
                "goto_shell",
                "app_frame",
                "dismiss_modals",
                "date_picker_近30天",
                "export_dropdown",
                ORDERS_EXPORT_MENU_ITEM,
                f"transport_center:{TRANSPORT_TASK_HINTS.orders}",
            ],
        )
        sources.append(orders)

        tms = _explore_export(
            page,
            run_dir,
            source="tms_inbound",
            export_name="tms_inbound.xlsx",
            export_fn=gerpgo_ui.scrape_tms_inbound,
            p0_aliases=TMS_P0_COLUMN_ALIASES,
            shot_prefix="tms",
            export_flow=[
                "login",
                "goto_shell",
                "app_frame",
                "dismiss_modals",
                "status_filter",
                "detail_scrape_产品收发货明细",
            ],
        )
        sources.append(tms)
        browser.close()

    core = [s for s in sources if s["source"] in ("erp_inventory", "erp_orders", "tms_inbound")]
    report = {
        "run_at": datetime.now(settings.tz).isoformat(),
        "erp_base": settings.erp_base_url,
        "overall": _overall(core),
        "sources": sources,
    }

    if args.ingest:
        from buque.db import SessionLocal

        db = SessionLocal()
        try:
            inv_file = run_dir / "exports" / "inventory_merged.xlsx"
            if not inv_file.exists():
                inv_file = run_dir / "exports" / "inventory_product.xlsx"
            result = run_ingestion_from_files(
                db,
                md,
                inventory_file=inv_file if inv_file.exists() else None,
                orders_file=run_dir / "exports" / "orders.xlsx",
                inbound_file=run_dir / "exports" / "tms_inbound.xlsx",
            )
            report["ingestion"] = [
                {"source": s.source, "status": s.status, "row_count": s.row_count, "error": s.error}
                for s in result.sources
            ]
        finally:
            db.close()

    (run_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_report_md(run_dir, report)
    print(f"\n探索完成: {run_dir}")
    print(f"整体结论: {report['overall']}")
    for s in core:
        print(f"  {s['source']}: {s['status']} rows={s.get('row_count', 0)}")
    if report["overall"] != "COMPLETE":
        sys.exit(1)


if __name__ == "__main__":
    main()
