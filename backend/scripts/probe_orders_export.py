#!/usr/bin/env python3
"""探测全渠道订单导出：传输中心入队 → 处理中 → 下载。

用法: cd backend && uv run python scripts/probe_orders_export.py [--headed] [--timeout-ms 900000]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import date, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from buque.config import get_settings
from buque.ingestion import gerpgo_ui
from buque.ingestion.erp_selectors import TRANSPORT_TASK_HINTS
from buque.ingestion.transport_center import find_pending_task, select_download_task

settings = get_settings()
OUT = Path(__file__).resolve().parents[1] / "data" / "probe_debug"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="探测全渠道订单导出传输中心协议")
    parser.add_argument("--headed", action="store_true", help="有头浏览器")
    parser.add_argument("--monitor-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--timeout-ms", type=int, default=settings.erp_orders_export_timeout_ms)
    parser.add_argument("--poll-interval", type=int, default=10, help="轮询间隔秒")
    args = parser.parse_args()

    if not settings.erp_base_url or not settings.erp_username:
        print("ERP_BASE_URL / ERP_USERNAME 未配置", file=sys.stderr)
        return 1

    run_id = datetime.now(settings.tz).strftime("%Y%m%d_%H%M%S")
    run_dir = OUT / f"orders_export_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    target = run_dir / "orders_probe.xlsx"
    task_hint = TRANSPORT_TASK_HINTS.orders

    report: dict = {
        "monitor_date": args.monitor_date.isoformat(),
        "timeout_ms": args.timeout_ms,
        "poll_interval_s": args.poll_interval,
        "timeline": [],
        "outcome": None,
        "error": None,
    }

    def log(event: str, **extra: object) -> None:
        entry = {"t": datetime.now(settings.tz).isoformat(), "event": event, **extra}
        report["timeline"].append(entry)
        print(json.dumps(entry, ensure_ascii=False))

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not args.headed)
            context = browser.new_context(accept_downloads=True, viewport={"width": 1920, "height": 1080})
            page = context.new_page()
            gerpgo_ui.login(page)

            gerpgo_ui.goto_shell(page, "/sales/multiChannel/orders")
            frame = gerpgo_ui.app_frame(page, "multiChannel/orders")
            gerpgo_ui.dismiss_interruptions(page, frame)
            gerpgo_ui.apply_orders_date_window(frame)
            gerpgo_ui.dismiss_interruptions(page, frame)

            before_ids = gerpgo_ui._snapshot_task_ids(page, task_hint)
            today = datetime.now(settings.tz).date()
            min_request_date = min(args.monitor_date, today)
            log("snapshot", before_ids=sorted(before_ids), min_request_date=min_request_date.isoformat())

            gerpgo_ui.goto_shell(page, "/sales/multiChannel/orders")
            frame = gerpgo_ui.app_frame(page, "multiChannel/orders")
            gerpgo_ui.dismiss_interruptions(page, frame)
            gerpgo_ui.apply_orders_date_window(frame)
            gerpgo_ui.dismiss_interruptions(page, frame)

            triggered_at = datetime.now(settings.tz)
            gerpgo_ui.trigger_orders_export(frame)
            gerpgo_ui.confirm_pending_export(page, frame)
            log("export_triggered", triggered_at=triggered_at.isoformat())

            deadline = time.time() + args.timeout_ms / 1000
            pending_task_id: str | None = None
            download_failures = 0

            while time.time() < deadline:
                tasks = gerpgo_ui._list_transport_tasks(page)
                pending = find_pending_task(
                    tasks,
                    hint=task_hint,
                    min_request_date=min_request_date,
                    before_task_ids=before_ids,
                )
                if pending is not None:
                    pending_task_id = pending.task_id
                log(
                    "poll",
                    pending_task_id=pending_task_id,
                    pending_status=pending.status if pending else None,
                    order_task_count=sum(1 for t in tasks if task_hint in t.task_type),
                )

                selected = select_download_task(
                    tasks,
                    hint=task_hint,
                    min_request_date=min_request_date,
                    before_task_ids=before_ids,
                )
                if selected is not None:
                    try:
                        with page.expect_download(timeout=60_000) as info:
                            gerpgo_ui._click_transport_download(page, selected.task_id)
                        info.value.save_as(str(target))
                        if target.exists() and target.stat().st_size > 0:
                            report["outcome"] = "downloaded"
                            report["task_id"] = selected.task_id
                            report["file"] = str(target)
                            report["file_bytes"] = target.stat().st_size
                            log("downloaded", task_id=selected.task_id, bytes=target.stat().st_size)
                            browser.close()
                            break
                        download_failures += 1
                        log("download_empty", task_id=selected.task_id)
                    except Exception as exc:
                        download_failures += 1
                        log("download_error", task_id=selected.task_id, error=str(exc))
                time.sleep(args.poll_interval)
            else:
                if pending_task_id is None:
                    report["outcome"] = "no_new_task"
                elif download_failures > 0:
                    report["outcome"] = "download_failed"
                else:
                    report["outcome"] = "processing_timeout"
                report["pending_task_id"] = pending_task_id
                report["download_failures"] = download_failures
                browser.close()

    except Exception as exc:
        report["outcome"] = "error"
        report["error"] = str(exc)
        report["traceback"] = traceback.format_exc()
        log("fatal", error=str(exc))

    report_path = run_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告: {report_path}")
    return 0 if report.get("outcome") == "downloaded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
