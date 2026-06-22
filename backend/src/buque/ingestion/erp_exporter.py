from __future__ import annotations

from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright
from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.ingestion.parsers import InboundParser, InventoryParser, OrdersParser
from buque.services.rule_config import RuleConfigService

settings = get_settings()


class ErpExporter:
    """ERP 页面导出：登录 → 导航 → 触发导出 → 落盘。"""

    ORDERS_PATH = "/sales/multiChannel/orders"
    INVENTORY_PATH = "/gip/inventoryManage/product"

    def __init__(self, export_dir: Path | None = None):
        self.export_dir = export_dir or Path(settings.export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def _login(self, page) -> None:
        if not settings.erp_base_url or not settings.erp_username:
            raise RuntimeError("ERP_BASE_URL / ERP_USERNAME 未配置")
        page.goto(f"{settings.erp_base_url.rstrip('/')}/login")
        page.fill('input[name="username"], input[type="text"]', settings.erp_username)
        page.fill('input[name="password"], input[type="password"]', settings.erp_password)
        page.click('button[type="submit"], .login-btn')
        page.wait_for_load_state("networkidle")

    def export_page(self, path_suffix: str, export_button_selector: str, filename: str) -> Path:
        target = self.export_dir / filename
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            self._login(page)
            page.goto(f"{settings.erp_base_url.rstrip('/')}{path_suffix}")
            page.wait_for_load_state("networkidle")
            with page.expect_download() as download_info:
                page.click(export_button_selector)
            download = download_info.value
            download.save_as(str(target))
            browser.close()
        return target


def run_ingestion_from_files(
    db: Session,
    monitor_date: date,
    inventory_file: Path | None = None,
    orders_file: Path | None = None,
    inbound_file: Path | None = None,
) -> dict[str, int]:
    rule_config = RuleConfigService(db)
    results: dict[str, int] = {}

    if inventory_file and inventory_file.exists():
        results["inventory"] = InventoryParser(db, monitor_date).ingest_file(inventory_file)
    if orders_file and orders_file.exists():
        results["orders"] = OrdersParser(db, monitor_date).ingest_file(orders_file)
    if inbound_file and inbound_file.exists():
        results["inbound"] = InboundParser(db, monitor_date, rule_config).ingest_file(inbound_file)

    return results


def run_ingestion_from_erp(db: Session, monitor_date: date) -> dict[str, int]:
    exporter = ErpExporter()
    inventory_path = exporter.export_page(
        ErpExporter.INVENTORY_PATH,
        'button:has-text("导出"), .export-btn',
        f"inventory_{monitor_date.isoformat()}.xlsx",
    )
    orders_path = exporter.export_page(
        ErpExporter.ORDERS_PATH,
        'button:has-text("导出"), .export-btn',
        f"orders_{monitor_date.isoformat()}.xlsx",
    )
    return run_ingestion_from_files(
        db,
        monitor_date,
        inventory_file=inventory_path,
        orders_file=orders_path,
    )
