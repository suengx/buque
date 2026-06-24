from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from buque.config import get_settings
from buque.ingestion import gerpgo_ui
from buque.ingestion.erp_selectors import INVENTORY_MULTI_PLATFORM_TABS, PATHS
from buque.ingestion.transport_center import TransportTaskMeta

settings = get_settings()


class GerpgGoSession:
    """单次登录、多页面导出的积加 ERP Playwright 会话。"""

    def __init__(self, export_dir: Path | None = None, headless: bool = True):
        self.export_dir = export_dir or Path(settings.export_dir)
        self.headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self.transport_metas: dict[str, TransportTaskMeta] = {}

    def __enter__(self) -> GerpgGoSession:
        if not settings.erp_base_url or not settings.erp_username:
            raise RuntimeError("ERP_BASE_URL / ERP_USERNAME 未配置")
        self._playwright = sync_playwright().start()
        launch_args = ["--no-sandbox", "--disable-dev-shm-usage"]
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=launch_args,
        )
        self._context = self._browser.new_context(accept_downloads=True, viewport={"width": 1920, "height": 1080})
        self._page = self._context.new_page()
        gerpgo_ui.login(self._page)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("会话未启动")
        return self._page

    def _archive_dir(self, monitor_date: date) -> Path:
        d = self.export_dir / monitor_date.isoformat()
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _timestamp_name(self, source: str, monitor_date: date, suffix: str = ".xlsx") -> Path:
        ts = datetime.now(settings.tz).strftime("%H%M%S")
        return self._archive_dir(monitor_date) / f"{source}_{ts}{suffix}"

    def export_inventory_product(self, monitor_date: date) -> Path:
        target = self._timestamp_name("inventory_product", monitor_date)
        _, _, _, meta = gerpgo_ui.export_inventory_product(self.page, target, monitor_date)
        self.transport_metas["erp_inventory"] = meta
        return target

    def export_inventory_multi_platform(self, monitor_date: date) -> list[Path]:
        files: list[Path] = []
        if INVENTORY_MULTI_PLATFORM_TABS:
            for tab_name in INVENTORY_MULTI_PLATFORM_TABS:
                safe = tab_name.replace(" ", "_")
                target = self._timestamp_name(f"inventory_{safe}", monitor_date)
                gerpgo_ui.export_inventory_multi_platform(self.page, target, monitor_date, tab_name=tab_name)
                files.append(target)
        else:
            target = self._timestamp_name("inventory_multi_platform", monitor_date)
            _, _, _, meta = gerpgo_ui.export_inventory_multi_platform(self.page, target, monitor_date)
            self.transport_metas["erp_inventory_multi"] = meta
            files.append(target)
        return files

    def export_orders(
        self,
        monitor_date: date,
        *,
        on_status: Callable[[str], None] | None = None,
    ) -> Path:
        target = self._timestamp_name("orders", monitor_date)
        _, _, _, meta = gerpgo_ui.export_orders(
            self.page, target, monitor_date, on_status=on_status
        )
        self.transport_metas["erp_orders"] = meta
        return target

    def export_tms_inbound(self, monitor_date: date) -> Path:
        target = self._timestamp_name("tms_inbound", monitor_date)
        gerpgo_ui.scrape_tms_inbound(self.page, target)
        return target

    def export_inventory_merged(self, monitor_date: date) -> Path:
        frames: list[pd.DataFrame] = []
        product = self.export_inventory_product(monitor_date)
        frames.append(self._read_export(product))
        if INVENTORY_MULTI_PLATFORM_TABS:
            for p in self.export_inventory_multi_platform(monitor_date):
                frames.append(self._read_export(p))
        merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        dedupe_cols = [c for c in ("SKU", "仓库") if c in merged.columns]
        if dedupe_cols:
            merged = merged.drop_duplicates(subset=dedupe_cols, keep="last")
        target = self._timestamp_name("inventory_merged", monitor_date)
        merged.to_excel(target, index=False)
        return target

    @staticmethod
    def _read_export(path: Path) -> pd.DataFrame:
        if path.suffix.lower() in {".xlsx", ".xls"}:
            return pd.read_excel(path)
        return pd.read_csv(path)
