#!/usr/bin/env python3
"""探测积加产品库存：页面表格 vs 批量导出 是否一致。

用法: cd backend && uv run python scripts/probe_inventory_discrepancy.py [--sku C0160370] [--warehouse SUNBURY]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from playwright.sync_api import Frame, Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from buque.config import get_settings
from buque.ingestion import gerpgo_ui
from buque.ingestion.erp_selectors import PATHS, TRANSPORT_TASK_HINTS

settings = get_settings()
OUT = Path(__file__).resolve().parents[1] / "data" / "probe_debug"
OUT.mkdir(parents=True, exist_ok=True)


def _find_sku_input(frame: Frame, sku: str) -> None:
    """在产品库存页填入 SKU 并查询。"""
    filled = False
    for loc in (
        frame.get_by_placeholder(re.compile(r"SKU|sku|产品", re.I)),
        frame.locator('input[placeholder*="SKU"]'),
        frame.locator('input[placeholder*="sku"]'),
        frame.locator(".arco-input:not([readonly])"),
    ):
        n = loc.count()
        for i in range(min(n, 8)):
            el = loc.nth(i)
            try:
                if not el.is_visible() or not el.is_enabled():
                    continue
                ph = el.get_attribute("placeholder") or ""
                if "店铺" in ph or "仓库" in ph:
                    continue
                el.fill(sku)
                filled = True
                break
            except Exception:
                continue
        if filled:
            break

    if not filled:
        sku_label = frame.get_by_text("SKU", exact=True)
        if sku_label.count():
            parent = sku_label.first.locator(
                "xpath=ancestor::div[contains(@class,'form') or contains(@class,'filter')][1]"
            )
            inp = parent.locator("input").first
            if inp.count():
                inp.fill(sku)
                filled = True

    if not filled:
        raise RuntimeError("未找到可编辑的 SKU 搜索框")

    for txt in ("查询", "搜索", "查 询"):
        btn = frame.get_by_role("button", name=re.compile(txt))
        if btn.count():
            btn.first.click()
            frame.wait_for_timeout(3500)
            return
    frame.keyboard.press("Enter")
    frame.wait_for_timeout(3500)


def _parse_table_rows(frame: Frame) -> list[dict[str, str]]:
    """从 ant-design/arco 表格解析可见行。"""
    rows: list[dict[str, str]] = []
    # 表头
    headers: list[str] = []
    for sel in (".arco-table-th", "thead th", ".ant-table-thead th"):
        ths = frame.locator(sel)
        if ths.count() >= 3:
            headers = [ths.nth(i).inner_text().strip().replace("\n", "") for i in range(ths.count())]
            break

    trs = frame.locator(".arco-table-tr:not(.arco-table-tr-empty), tbody tr")
    count = trs.count()
    for i in range(count):
        tr = trs.nth(i)
        cells = tr.locator("td")
        if cells.count() < 3:
            continue
        texts = [cells.nth(j).inner_text().strip().replace("\n", " ") for j in range(cells.count())]
        if not any(texts):
            continue
        if headers and len(headers) == len(texts):
            rows.append(dict(zip(headers, texts)))
        else:
            rows.append({"_raw": " | ".join(texts), "_cells": texts})
    return rows


def _pick_row(rows: list[dict], sku: str, warehouse_hint: str) -> dict | None:
    for row in rows:
        blob = json.dumps(row, ensure_ascii=False)
        if sku in blob and warehouse_hint in blob:
            return row
    for row in rows:
        if warehouse_hint in json.dumps(row, ensure_ascii=False):
            return row
    return None


def _read_export_row(path: Path, sku: str, warehouse_hint: str) -> dict | None:
    df = pd.read_excel(path)
    mask = (df["SKU"].astype(str) == sku) & df["仓库"].astype(str).str.contains(warehouse_hint, na=False)
    if not mask.any():
        return None
    r = df[mask].iloc[0]
    return {k: (None if pd.isna(v) else v) for k, v in r.items()}


def _capture_transport_tasks(page: Page) -> list[str]:
    texts: list[str] = []
    try:
        tc = gerpgo_ui._open_transport_center(page)
        downloads = tc.get_by_text("下载", exact=True)
        for i in range(min(downloads.count(), 8)):
            texts.append(gerpgo_ui._download_row_text(tc, i))
    except Exception as exc:
        texts.append(f"ERROR: {exc}")
    return texts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sku", default="C0160370")
    parser.add_argument("--warehouse", default="SUNBURY")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    if not settings.erp_base_url:
        print("ERP 未配置")
        sys.exit(1)

    ts = datetime.now(settings.tz).strftime("%Y%m%d_%H%M%S")
    run_dir = OUT / f"discrepancy_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    export_path = run_dir / "inventory_product_probe.xlsx"

    report: dict = {
        "run_at": datetime.now(settings.tz).isoformat(),
        "sku": args.sku,
        "warehouse_hint": args.warehouse,
        "steps": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        gerpgo_ui.login(page)
        gerpgo_ui.goto_shell(page, PATHS.inventory_product)
        frame = gerpgo_ui.app_frame(page, "inventoryManage/product")
        gerpgo_ui.dismiss_interruptions(page, frame)

        page.screenshot(path=str(run_dir / "01_initial.png"), full_page=True)
        report["shell_url"] = page.url
        report["iframe_url"] = frame.url

        # Step 1: 无筛选全表抽样（看 SUNBURY 是否在默认视图）
        rows_before = _parse_table_rows(frame)
        row_before = _pick_row(rows_before, args.sku, args.warehouse)
        report["steps"].append(
            {
                "phase": "ui_before_search",
                "row_count": len(rows_before),
                "target_row": row_before,
            }
        )

        # Step 2: 搜索 SKU 后读表
        try:
            _find_sku_input(frame, args.sku)
            gerpgo_ui.dismiss_interruptions(page, frame)
            page.screenshot(path=str(run_dir / "02_after_search.png"), full_page=True)
            rows_searched = _parse_table_rows(frame)
            row_searched = _pick_row(rows_searched, args.sku, args.warehouse)
            report["steps"].append(
                {
                    "phase": "ui_after_search",
                    "row_count": len(rows_searched),
                    "target_row": row_searched,
                    "all_rows_sample": rows_searched[:6],
                }
            )
        except Exception as exc:
            report["steps"].append({"phase": "ui_after_search", "error": str(exc)})
            rows_searched = []
            row_searched = None

        # Step 3: 自定义导出入口 + 传输中心下载
        export_started = datetime.now(settings.tz).isoformat()
        try:
            before_ids = gerpgo_ui._snapshot_task_ids(page, TRANSPORT_TASK_HINTS.inventory)
            report["steps"].append({"phase": "tc_before_export", "task_ids": sorted(before_ids)})
            _, _, _, meta = gerpgo_ui.export_inventory_product(page, export_path, date.today())
            export_finished = datetime.now(settings.tz).isoformat()
            after_ids = gerpgo_ui._snapshot_task_ids(page, TRANSPORT_TASK_HINTS.inventory)
            new_ids = sorted(after_ids - before_ids)
            export_row = _read_export_row(export_path, args.sku, args.warehouse)
            report["steps"].append(
                {
                    "phase": "export",
                    "started_at": export_started,
                    "finished_at": export_finished,
                    "transport_task_id": meta.task_id,
                    "transport_requested_at": meta.requested_at.isoformat(),
                    "file_sha256": meta.file_sha256,
                    "new_task_ids": new_ids,
                    "file": str(export_path),
                    "file_mtime": datetime.fromtimestamp(export_path.stat().st_mtime, settings.tz).isoformat(),
                    "file_size": export_path.stat().st_size,
                    "target_row": {
                        "可用量": export_row.get("可用量") if export_row else None,
                        "7天日均": export_row.get("7天日均") if export_row else None,
                        "MSKU": export_row.get("MSKU") if export_row else None,
                        "更新时间": str(export_row.get("更新时间")) if export_row else None,
                        "创建时间": str(export_row.get("创建时间")) if export_row else None,
                    },
                }
            )
        except Exception as exc:
            report["steps"].append({"phase": "export", "error": str(exc)})
            export_row = None

        # Step 4: 导出后再读 UI（是否被搜索条件影响）
        try:
            gerpgo_ui.goto_shell(page, PATHS.inventory_product)
            frame2 = gerpgo_ui.app_frame(page, "inventoryManage/product")
            gerpgo_ui.dismiss_interruptions(page, frame2)
            _find_sku_input(frame2, args.sku)
            rows_after = _parse_table_rows(frame2)
            row_after = _pick_row(rows_after, args.sku, args.warehouse)
            report["steps"].append(
                {
                    "phase": "ui_after_export",
                    "row_count": len(rows_after),
                    "target_row": row_after,
                }
            )
        except Exception as exc:
            report["steps"].append({"phase": "ui_after_export", "error": str(exc)})

        report["transport_center_tasks"] = _capture_transport_tasks(page)
        page.screenshot(path=str(run_dir / "03_transport_center.png"), full_page=True)
        browser.close()

    # 对比结论
    def _avail(step: dict) -> str | None:
        row = step.get("target_row")
        if not row:
            return None
        if "可用量" in row:
            return str(row["可用量"])
        raw = row.get("_raw") or json.dumps(row, ensure_ascii=False)
        m = re.search(r"(\d+)\s+(\d+)\s+(\d+)", raw)
        return raw if not m else None

    ui_row = next((s for s in report["steps"] if s.get("phase") == "ui_after_search" and s.get("target_row")), {})
    exp_row = next((s for s in report["steps"] if s.get("phase") == "export" and s.get("target_row")), {})

    report["conclusion"] = {
        "ui_available": ui_row.get("target_row", {}).get("可用量") if ui_row.get("target_row") else ui_row.get("error"),
        "export_available": exp_row.get("target_row", {}).get("可用量") if exp_row.get("target_row") else exp_row.get("error"),
        "export_row_更新时间": exp_row.get("target_row", {}).get("更新时间"),
        "export_file_mtime": exp_row.get("file_mtime"),
        "export_finished_at": exp_row.get("finished_at"),
        "match": None,
    }
    ui_a = report["conclusion"]["ui_available"]
    ex_a = report["conclusion"]["export_available"]
    if ui_a is not None and ex_a is not None:
        try:
            report["conclusion"]["match"] = float(ui_a) == float(ex_a)
        except (TypeError, ValueError):
            report["conclusion"]["match"] = str(ui_a) == str(ex_a)

    out_json = run_dir / "report.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report["conclusion"], ensure_ascii=False, indent=2))
    print(f"\n完整报告: {out_json}")
    print(f"截图目录: {run_dir}")


if __name__ == "__main__":
    main()
