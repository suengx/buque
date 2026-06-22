from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd
from playwright.sync_api import Frame, Page, TimeoutError as PlaywrightTimeout

from buque.config import get_settings
from buque.ingestion.erp_selectors import (
    APP_FRAME_URL_CONTAINS,
    DISMISS_TEXTS,
    LOGIN_PATH,
    ORDERS_DATE_QUICK_LABELS,
    ORDERS_EXPORT_MENU_ITEM,
    SELECTORS,
    TMS_DETAIL_RECEIPT_TAB,
    TMS_ELIGIBLE_STATUSES,
    TMS_LIST_BATCH_PATTERN,
    TRANSPORT_TASK_HINTS,
    WEB_PREFIX,
)

settings = get_settings()


def erp_base() -> str:
    return settings.erp_base_url.rstrip("/")


def shell_url(path: str) -> str:
    prefix = settings.erp_web_prefix or WEB_PREFIX
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{erp_base()}{prefix}{path}"


def app_url(path: str) -> str:
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{erp_base()}/amzv-app{path}"


def login(page: Page) -> None:
    page.goto(f"{erp_base()}{LOGIN_PATH}", timeout=60_000)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)
    page.locator(SELECTORS.username).fill(settings.erp_username)
    page.locator(SELECTORS.password).fill(settings.erp_password)
    page.locator(SELECTORS.login_submit).click()
    page.wait_for_load_state("networkidle", timeout=60_000)
    page.wait_for_timeout(2000)


def goto_shell(page: Page, path: str) -> str:
    url = shell_url(path)
    page.goto(url, timeout=60_000)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3000)
    return url


def app_frame(page: Page, path_hint: str = "", timeout_ms: int = 60_000) -> Frame:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for frame in page.frames:
            url = frame.url or ""
            if APP_FRAME_URL_CONTAINS not in url:
                continue
            if path_hint and path_hint not in url:
                continue
            try:
                if frame.locator("body").count() > 0:
                    return frame
            except Exception:
                continue
        page.wait_for_timeout(500)
    raise RuntimeError(f"未找到 amzv-app iframe (hint={path_hint})")


def dismiss_interruptions(page: Page, frame: Frame | None = None, rounds: int = 5) -> list[str]:
    seen: list[str] = []
    scopes: list[Page | Frame] = [page]
    if frame:
        scopes.append(frame)

    for _ in range(rounds):
        acted = False
        for scope in scopes:
            for text in DISMISS_TEXTS:
                loc = scope.get_by_text(text, exact=False)
                if loc.count() == 0:
                    continue
                try:
                    loc.first.click(timeout=1500, force=True)
                    seen.append(text)
                    acted = True
                    scope.wait_for_timeout(400)
                except Exception:
                    pass
            for sel in (SELECTORS.modal_close, SELECTORS.mask):
                loc = scope.locator(sel)
                if loc.count() == 0:
                    continue
                try:
                    loc.first.click(timeout=1000, force=True)
                    seen.append(sel)
                    acted = True
                    scope.wait_for_timeout(300)
                except Exception:
                    pass
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        if not acted:
            break
    return seen


def _open_transport_center(page: Page) -> Frame:
    icon = page.locator(SELECTORS.transport_center_icon).first
    icon.wait_for(state="visible", timeout=30_000)
    icon.click()
    page.wait_for_timeout(2500)
    dismiss_interruptions(page)
    return app_frame(page, "transmission-center")


def _download_row_text(frame: Frame, index: int) -> str:
    dl = frame.get_by_text("下载", exact=True).nth(index)
    row = dl.locator('xpath=ancestor::*[contains(@class,"row") or contains(@class,"tr")][1]')
    if row.count() == 0:
        row = dl.locator("xpath=ancestor::tr[1]")
    return row.inner_text() if row.count() else dl.inner_text()


def download_from_transport_center(
    page: Page,
    target: Path,
    task_hint: str = "",
    timeout_ms: int | None = None,
) -> Path:
    timeout = timeout_ms or settings.erp_sync_timeout_ms
    deadline = time.time() + timeout / 1000
    started = time.time()

    while time.time() < deadline:
        dismiss_interruptions(page)
        tc = _open_transport_center(page)
        dismiss_interruptions(page, tc)
        downloads = tc.get_by_text("下载", exact=True)
        count = downloads.count()
        best_idx: int | None = None
        best_text = ""

        for i in range(count):
            text = _download_row_text(tc, i)
            if task_hint and task_hint not in text:
                continue
            if "处理中" in text or "失败" in text:
                continue
            if "已完成" not in text and "完成" not in text:
                continue
            best_idx = i
            best_text = text
            break

        if best_idx is not None:
            try:
                with page.expect_download(timeout=60_000) as info:
                    downloads.nth(best_idx).click(force=True)
                info.value.save_as(str(target))
                if target.exists() and target.stat().st_size > 0:
                    return target
            except Exception:
                dismiss_interruptions(page, tc)

        elapsed = int(time.time() - started)
        if elapsed > 30 and elapsed % 30 < 4:
            page.wait_for_timeout(5000)
        else:
            page.wait_for_timeout(3000)

    raise RuntimeError(f"传输中心下载超时 (hint={task_hint}, waited={int(time.time()-started)}s)")


def click_import_export(frame: Frame) -> None:
    menu = frame.locator(SELECTORS.import_export_menu).first
    menu.wait_for(state="visible", timeout=30_000)
    menu.click(force=True)
    frame.wait_for_timeout(800)


def click_export_button(frame: Frame) -> None:
    btn = frame.get_by_role("button", name=SELECTORS.export_button_role, exact=True)
    btn.wait_for(state="visible", timeout=15_000)
    btn.click()


def click_direct_export(frame: Frame) -> None:
    btn = frame.get_by_role("button", name=SELECTORS.export_button_role, exact=True)
    btn.wait_for(state="visible", timeout=30_000)
    btn.click()


def apply_orders_date_window(frame: Frame) -> None:
    picker = frame.locator(SELECTORS.orders_date_picker).first
    picker.wait_for(state="attached", timeout=15_000)
    picker.click(force=True)
    frame.wait_for_timeout(800)
    for label in ORDERS_DATE_QUICK_LABELS:
        loc = frame.get_by_text(label, exact=False)
        if loc.count() == 0:
            continue
        loc.first.click(force=True)
        frame.wait_for_timeout(500)
        break
    confirm = frame.get_by_role("button", name="确认")
    if confirm.count():
        confirm.first.click(force=True)
    frame.wait_for_timeout(2000)


def trigger_orders_export(frame: Frame) -> None:
    frame.get_by_role("button", name=SELECTORS.export_button_role, exact=True).click()
    frame.wait_for_timeout(800)
    frame.get_by_text(ORDERS_EXPORT_MENU_ITEM, exact=True).first.click()
    frame.wait_for_timeout(1200)
    frame.get_by_role("button", name=SELECTORS.export_button_role).last.click()


def apply_tms_status_filters(frame: Frame) -> None:
    for status in TMS_ELIGIBLE_STATUSES:
        loc = frame.get_by_text(status, exact=True)
        if loc.count() == 0:
            continue
        try:
            loc.first.click(timeout=2000, force=True)
            frame.wait_for_timeout(500)
        except Exception:
            pass
    frame.wait_for_timeout(1500)


def _try_immediate_download(page: Page, target: Path, action) -> bool:
    try:
        with page.expect_download(timeout=8_000) as info:
            action()
        info.value.save_as(str(target))
        return target.exists() and target.stat().st_size > 0
    except PlaywrightTimeout:
        return False


def export_inventory_product(page: Page, target: Path) -> tuple[str, str, list[str]]:
    url = goto_shell(page, "/gip/inventoryManage/product")
    frame = app_frame(page, "inventoryManage/product")
    popups = dismiss_interruptions(page, frame)
    dismiss_interruptions(page, frame)

    def _export():
        click_import_export(frame)
        click_export_button(frame)

    if not _try_immediate_download(page, target, _export):
        _export()
        download_from_transport_center(page, target, task_hint=TRANSPORT_TASK_HINTS.inventory)
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"库存导出无效: {target}")
    return url, frame.url, popups


def export_inventory_multi_platform(page: Page, target: Path, tab_name: str | None = None) -> tuple[str, str, list[str]]:
    url = goto_shell(page, "/gip/inventoryManage/multiPlatform")
    frame = app_frame(page, "multiPlatform")
    popups = dismiss_interruptions(page, frame)
    if tab_name:
        tab = frame.get_by_text(tab_name, exact=False)
        if tab.count():
            tab.first.click(force=True)
            frame.wait_for_timeout(1500)
    dismiss_interruptions(page, frame)

    def _export():
        click_direct_export(frame)

    if not _try_immediate_download(page, target, _export):
        _export()
        download_from_transport_center(page, target, task_hint=TRANSPORT_TASK_HINTS.inventory)
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"multiPlatform 导出无效: {target}")
    return url, frame.url, popups


def export_orders(page: Page, target: Path) -> tuple[str, str, list[str]]:
    url = goto_shell(page, "/sales/multiChannel/orders")
    frame = app_frame(page, "multiChannel/orders")
    popups = dismiss_interruptions(page, frame)
    apply_orders_date_window(frame)
    dismiss_interruptions(page, frame)

    def _export():
        trigger_orders_export(frame)

    if not _try_immediate_download(page, target, _export):
        _export()
        download_from_transport_center(page, target, task_hint=TRANSPORT_TASK_HINTS.orders)
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"订单导出无效: {target}")
    return url, frame.url, popups


def _parse_tms_receipt_tab(body: str, batch_id: str, warehouse: str, tms_status: str) -> list[dict[str, object]]:
    marker = "未收量"
    idx = body.find(marker)
    if idx < 0:
        return []
    lines = [ln.strip() for ln in body[idx:].splitlines() if ln.strip()]
    sku_re = re.compile(r"^C[A-Z0-9]{4,}$")
    rows: list[dict[str, object]] = []
    i = 0
    while i < len(lines):
        if not sku_re.match(lines[i]):
            i += 1
            continue
        sku = lines[i]
        j = i + 1
        dash_indices: list[int] = []
        while j < len(lines):
            if sku_re.match(lines[j]):
                break
            if lines[j] == "--":
                dash_indices.append(j)
            j += 1
        unreceived = 0
        if dash_indices:
            dash_idx = dash_indices[-1]
            nums: list[int] = []
            k = dash_idx + 1
            while k < len(lines) and len(nums) < 6:
                if re.fullmatch(r"-?\d+", lines[k]):
                    nums.append(int(lines[k]))
                elif sku_re.match(lines[k]):
                    break
                k += 1
            if len(nums) >= 6:
                unreceived = nums[5]
        rows.append(
            {
                "sku": sku,
                "warehouse": warehouse,
                "batch_id": batch_id,
                "tms_status": tms_status,
                "unreceived_qty": unreceived,
            }
        )
        i = j if j > i else i + 1
    return rows


def scrape_tms_inbound(page: Page, target: Path) -> tuple[str, str, list[str]]:
    shell_path = "/tms/logisticsBill"
    url = goto_shell(page, shell_path)
    frame = app_frame(page, "logisticsBill")
    popups = dismiss_interruptions(page, frame)
    apply_tms_status_filters(frame)
    dismiss_interruptions(page, frame)
    body = frame.locator("body").inner_text()
    batches = re.findall(TMS_LIST_BATCH_PATTERN, body)
    eligible = [b for b in dict.fromkeys(batches) if any(s in body for s in TMS_ELIGIBLE_STATUSES)]
    records: list[dict[str, object]] = []

    detail_links = frame.get_by_text("详情", exact=True)
    count = min(detail_links.count(), len(eligible), 20)

    for i in range(count):
        dismiss_interruptions(page, frame)
        detail_links.nth(i).click(force=True)
        page.wait_for_timeout(3500)
        detail = app_frame(page, "logisticsBill/view")
        dismiss_interruptions(page, detail)
        detail_body = detail.locator("body").inner_text()
        batch_id = eligible[i] if i < len(eligible) else ""
        code_match = re.search(r"DL\d{10}", detail_body)
        if code_match:
            batch_id = code_match.group(0)
        warehouse = ""
        wh_match = re.search(r"目的仓\s*[:：]\s*([^\n]+)", detail_body)
        if wh_match:
            warehouse = wh_match.group(1).strip()
        status = ""
        for s in TMS_ELIGIBLE_STATUSES:
            if s in detail_body:
                status = s
                break
        tab = detail.get_by_text(TMS_DETAIL_RECEIPT_TAB, exact=False)
        if tab.count():
            tab.first.click(force=True)
            detail.wait_for_timeout(2000)
        receipt_body = detail.locator("body").inner_text()
        records.extend(_parse_tms_receipt_tab(receipt_body, batch_id, warehouse, status))

        page.goto(url, timeout=60_000)
        frame = app_frame(page, "logisticsBill")
        dismiss_interruptions(page, frame)
        apply_tms_status_filters(frame)
        detail_links = frame.get_by_text("详情", exact=True)

    df = pd.DataFrame(records)
    if not df.empty:
        df = (
            df.groupby(["batch_id", "sku", "warehouse", "tms_status"], as_index=False)
            .agg({"unreceived_qty": "max"})
        )
    if target.suffix.lower() in {".xlsx", ".xls"}:
        df.to_excel(target, index=False)
    else:
        df.to_csv(target, index=False)
    return url, frame.url, popups


# 兼容 explore_erp / session 旧入口
def export_page_to_file(
    page: Page,
    shell_path: str,
    target: Path,
    *,
    path_hint: str = "",
    task_hint: str = "",
    before_export=None,
    export_mode: str = "import_export",
) -> tuple[str, str, list[str]]:
    if export_mode == "orders":
        return export_orders(page, target)
    if export_mode == "direct":
        url = goto_shell(page, shell_path)
        frame = app_frame(page, path_hint=path_hint or shell_path.strip("/").split("/")[-1])
        popups = dismiss_interruptions(page, frame)
        if before_export:
            before_export(frame)
        dismiss_interruptions(page, frame)

        def _export():
            click_direct_export(frame)

        if not _try_immediate_download(page, target, _export):
            _export()
            download_from_transport_center(page, target, task_hint=task_hint)
        if not target.exists() or target.stat().st_size == 0:
            raise RuntimeError(f"导出文件无效: {target}")
        return url, frame.url, popups
    if export_mode == "tms_scrape":
        return scrape_tms_inbound(page, target)

    url = goto_shell(page, shell_path)
    frame = app_frame(page, path_hint=path_hint or shell_path.strip("/").split("/")[-1])
    popups = dismiss_interruptions(page, frame)
    if before_export:
        before_export(frame)
    dismiss_interruptions(page, frame)

    def _export():
        click_import_export(frame)
        click_export_button(frame)

    if not _try_immediate_download(page, target, _export):
        _export()
        download_from_transport_center(page, target, task_hint=task_hint)
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"导出文件无效: {target}")
    return url, frame.url, popups
