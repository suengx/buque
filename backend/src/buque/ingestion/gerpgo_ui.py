from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from playwright.sync_api import Frame, Page

from buque.config import get_settings
from buque.ingestion.erp_selectors import (
    APP_FRAME_URL_CONTAINS,
    DISMISS_TEXTS,
    INVENTORY_CUSTOM_EXPORT_MENU_ITEM,
    INVENTORY_CUSTOM_EXPORT_MODAL_TITLE,
    INVENTORY_CUSTOM_EXPORT_RESTORE_DEFAULT,
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
from buque.ingestion.transport_center import (
    PROCESSING_STATUSES,
    TransportTask,
    TransportTaskMeta,
    file_sha256,
    find_pending_task,
    parse_transport_row,
    select_download_task,
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
    dismiss_interruptions(page)
    url = shell_url(SELECTORS.transport_center_path)
    page.goto(url, timeout=60_000)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    dismiss_interruptions(page)
    return app_frame(page, "transmission-center")


def _download_row_text(frame: Frame, index: int) -> str:
    dl = frame.get_by_text("下载", exact=True).nth(index)
    row = dl.locator('xpath=ancestor::*[contains(@class,"row") or contains(@class,"tr")][1]')
    if row.count() == 0:
        row = dl.locator("xpath=ancestor::tr[1]")
    return row.inner_text() if row.count() else dl.inner_text()


def _list_transport_tasks(page: Page) -> list[TransportTask]:
    tc = _open_transport_center(page)
    dismiss_interruptions(page, tc)
    downloads = tc.get_by_text("下载", exact=True)
    tasks: list[TransportTask] = []
    for i in range(downloads.count()):
        text = _download_row_text(tc, i)
        task = parse_transport_row(text, row_index=i, tz=settings.tz)
        if task is not None:
            tasks.append(task)
    return tasks


def _snapshot_task_ids(page: Page, task_hint: str) -> set[str]:
    return {t.task_id for t in _list_transport_tasks(page) if task_hint in t.task_type}


def _click_transport_download(page: Page, task_id: str) -> None:
    tc = _open_transport_center(page)
    dismiss_interruptions(page, tc)
    downloads = tc.get_by_text("下载", exact=True)
    for i in range(downloads.count()):
        text = _download_row_text(tc, i)
        if text.startswith(task_id):
            downloads.nth(i).click(force=True)
            return
    raise RuntimeError(f"传输中心未找到任务 {task_id}")


def download_fresh_transport_task(
    page: Page,
    target: Path,
    *,
    task_hint: str,
    min_request_date: date,
    before_task_ids: set[str],
    export_trigger: Callable[[], None],
    timeout_ms: int | None = None,
    on_status: Callable[[str], None] | None = None,
    max_download_retries: int = 3,
) -> TransportTaskMeta:
    timeout = timeout_ms or settings.erp_sync_timeout_ms
    deadline = time.time() + timeout / 1000
    started = time.time()

    export_trigger()

    last_seen: list[TransportTask] = []
    pending_task: TransportTask | None = None
    last_status_log = 0.0
    download_task_id: str | None = None
    download_failures = 0
    last_download_error = ""

    while time.time() < deadline:
        dismiss_interruptions(page)
        tasks = _list_transport_tasks(page)
        last_seen = [t for t in tasks if task_hint in t.task_type]
        pending = find_pending_task(
            tasks,
            hint=task_hint,
            min_request_date=min_request_date,
            before_task_ids=before_task_ids,
        )
        if pending is not None:
            pending_task = pending

        elapsed = int(time.time() - started)
        if on_status and elapsed - last_status_log >= 30:
            if pending_task is not None:
                on_status(
                    f"等待传输中心任务 {pending_task.task_id} {pending_task.status}… "
                    f"(已等待 {elapsed}s)"
                )
            else:
                on_status(
                    f"轮询传输中心等待新任务 {task_hint}… "
                    f"(已等待 {elapsed}s, 可见 {len(last_seen)} 条)"
                )
            last_status_log = elapsed

        selected = select_download_task(
            tasks,
            hint=task_hint,
            min_request_date=min_request_date,
            before_task_ids=before_task_ids,
        )
        if selected is not None:
            if download_task_id != selected.task_id:
                download_task_id = selected.task_id
                download_failures = 0
            try:
                with page.expect_download(timeout=60_000) as info:
                    _click_transport_download(page, selected.task_id)
                info.value.save_as(str(target))
                if target.exists() and target.stat().st_size > 0:
                    return TransportTaskMeta(
                        task_id=selected.task_id,
                        requested_at=selected.requested_at,
                        task_type=selected.task_type,
                        file_sha256=file_sha256(target),
                    )
                last_download_error = f"文件为空: {target}"
            except Exception as exc:
                last_download_error = str(exc)
                dismiss_interruptions(page)
            download_failures += 1
            if on_status:
                on_status(
                    f"传输中心下载失败 task={selected.task_id} "
                    f"({download_failures}/{max_download_retries}): {last_download_error}"
                )
            if download_failures >= max_download_retries:
                raise RuntimeError(
                    f"传输中心下载失败 (task_id={selected.task_id}, "
                    f"retries={download_failures}, error={last_download_error})"
                )

        if elapsed > 30 and elapsed % 30 < 4:
            page.wait_for_timeout(5000)
        else:
            page.wait_for_timeout(3000)

    waited = int(time.time() - started)
    latest = max((t.requested_at for t in last_seen), default=None)
    base = (
        f"hint={task_hint}, min_date={min_request_date}, "
        f"before_ids={sorted(before_task_ids)}, latest_seen={latest}, waited={waited}s"
    )
    if pending_task is not None and pending_task.status in PROCESSING_STATUSES:
        raise RuntimeError(
            f"传输中心新任务处理超时 (task_id={pending_task.task_id}, "
            f"status={pending_task.status}, {base})"
        )
    if download_failures > 0 and download_task_id:
        raise RuntimeError(
            f"传输中心下载失败 (task_id={download_task_id}, "
            f"retries={download_failures}, error={last_download_error}, {base})"
        )
    try:
        page.screenshot(path=str(settings.export_dir / "transport_timeout.png"), full_page=True)
    except Exception:
        pass
    raise RuntimeError(f"传输中心未检测到新导出任务 ({base})")


def confirm_pending_export(page: Page, frame: Frame | None = None) -> None:
    scopes: list[Page | Frame] = [page]
    if frame is not None:
        scopes.insert(0, frame)
    for scope in scopes:
        for label in ("确认", "确定"):
            btn = scope.get_by_role("button", name=label)
            if btn.count() == 0:
                continue
            try:
                btn.first.click(timeout=2000, force=True)
                scope.wait_for_timeout(800)
                return
            except Exception:
                pass


def trigger_inventory_custom_export(frame: Frame) -> None:
    """产品库存页：导出下拉 → 自定义导出 → 弹窗导出（传输中心入队）。"""
    export_btn = frame.get_by_role("button", name=SELECTORS.export_button_role, exact=True)
    export_btn.first.wait_for(state="visible", timeout=30_000)
    export_btn.first.click(force=True)
    frame.wait_for_timeout(800)

    custom_item = frame.get_by_text(INVENTORY_CUSTOM_EXPORT_MENU_ITEM, exact=True)
    custom_item.first.wait_for(state="visible", timeout=15_000)
    custom_item.first.click(force=True)
    frame.wait_for_timeout(1200)

    modal = frame.locator(".arco-modal").filter(has_text=INVENTORY_CUSTOM_EXPORT_MODAL_TITLE)
    modal.first.wait_for(state="visible", timeout=15_000)

    restore = modal.get_by_text(INVENTORY_CUSTOM_EXPORT_RESTORE_DEFAULT, exact=True)
    if restore.count():
        restore.first.click(force=True)
        frame.wait_for_timeout(500)

    modal.get_by_role("button", name=SELECTORS.export_button_role, exact=True).last.click(force=True)
    frame.wait_for_timeout(1200)


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
    export_btn = frame.get_by_role("button", name=SELECTORS.export_button_role, exact=True)
    export_btn.first.wait_for(state="visible", timeout=30_000)
    export_btn.first.click(force=True)
    frame.wait_for_timeout(800)
    menu_item = frame.get_by_text(ORDERS_EXPORT_MENU_ITEM, exact=True).first
    menu_item.wait_for(state="visible", timeout=15_000)
    menu_item.click(force=True)
    frame.wait_for_timeout(1200)
    frame.get_by_role("button", name=SELECTORS.export_button_role).last.click(force=True)
    frame.wait_for_timeout(1200)


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


def _fresh_export(
    page: Page,
    target: Path,
    monitor_date: date,
    task_hint: str,
    shell_path: str,
    frame_hint: str,
    export_trigger: Callable[[Frame], None],
    prepare_frame: Callable[[Frame], None] | None = None,
    timeout_ms: int | None = None,
    on_status: Callable[[str], None] | None = None,
) -> TransportTaskMeta:
    goto_shell(page, shell_path)
    frame = app_frame(page, frame_hint)
    dismiss_interruptions(page, frame)
    if prepare_frame:
        prepare_frame(frame)
        dismiss_interruptions(page, frame)
    before_ids = _snapshot_task_ids(page, task_hint)
    goto_shell(page, shell_path)
    frame = app_frame(page, frame_hint)
    dismiss_interruptions(page, frame)
    if prepare_frame:
        prepare_frame(frame)
        dismiss_interruptions(page, frame)

    today = datetime.now(settings.tz).date()
    min_request_date = min(monitor_date, today)

    def _trigger() -> None:
        frame = app_frame(page, frame_hint)
        export_trigger(frame)
        confirm_pending_export(page, frame)

    return download_fresh_transport_task(
        page,
        target,
        task_hint=task_hint,
        min_request_date=min_request_date,
        before_task_ids=before_ids,
        export_trigger=_trigger,
        timeout_ms=timeout_ms,
        on_status=on_status,
    )


def export_inventory_product(
    page: Page, target: Path, monitor_date: date
) -> tuple[str, str, list[str], TransportTaskMeta]:
    url = goto_shell(page, "/gip/inventoryManage/product")
    frame = app_frame(page, "inventoryManage/product")
    popups = dismiss_interruptions(page, frame)
    dismiss_interruptions(page, frame)

    def _trigger_inventory(frame: Frame) -> None:
        trigger_inventory_custom_export(frame)

    meta = _fresh_export(
        page,
        target,
        monitor_date,
        TRANSPORT_TASK_HINTS.inventory,
        "/gip/inventoryManage/product",
        "inventoryManage/product",
        _trigger_inventory,
    )
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"库存导出无效: {target}")
    return url, frame.url, popups, meta


def export_inventory_multi_platform(
    page: Page, target: Path, monitor_date: date, tab_name: str | None = None
) -> tuple[str, str, list[str], TransportTaskMeta]:
    url = goto_shell(page, "/gip/inventoryManage/multiPlatform")
    frame = app_frame(page, "multiPlatform")
    popups = dismiss_interruptions(page, frame)
    if tab_name:
        tab = frame.get_by_text(tab_name, exact=False)
        if tab.count():
            tab.first.click(force=True)
            frame.wait_for_timeout(1500)
    dismiss_interruptions(page, frame)

    def _trigger(f: Frame) -> None:
        if tab_name:
            tab = f.get_by_text(tab_name, exact=False)
            if tab.count():
                tab.first.click(force=True)
                f.wait_for_timeout(1500)
        click_direct_export(f)

    meta = _fresh_export(
        page,
        target,
        monitor_date,
        TRANSPORT_TASK_HINTS.inventory,
        "/gip/inventoryManage/multiPlatform",
        "multiPlatform",
        _trigger,
    )
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"multiPlatform 导出无效: {target}")
    return url, frame.url, popups, meta


def export_orders(
    page: Page,
    target: Path,
    monitor_date: date,
    *,
    on_status: Callable[[str], None] | None = None,
) -> tuple[str, str, list[str], TransportTaskMeta]:
    url = goto_shell(page, "/sales/multiChannel/orders")
    frame = app_frame(page, "multiChannel/orders")
    popups = dismiss_interruptions(page, frame)
    apply_orders_date_window(frame)
    dismiss_interruptions(page, frame)

    meta = _fresh_export(
        page,
        target,
        monitor_date,
        TRANSPORT_TASK_HINTS.orders,
        "/sales/multiChannel/orders",
        "multiChannel/orders",
        trigger_orders_export,
        prepare_frame=apply_orders_date_window,
        timeout_ms=settings.erp_orders_export_timeout_ms,
        on_status=on_status,
    )
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"订单导出无效: {target}")
    return url, frame.url, popups, meta


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
    monitor_date: date | None = None,
) -> tuple[str, str, list[str], TransportTaskMeta | None]:
    md = monitor_date or datetime.now(settings.tz).date()
    if export_mode == "orders":
        return export_orders(page, target, md)
    if export_mode == "direct":
        url = goto_shell(page, shell_path)
        frame = app_frame(page, path_hint=path_hint or shell_path.strip("/").split("/")[-1])
        popups = dismiss_interruptions(page, frame)
        hint = path_hint or shell_path.strip("/").split("/")[-1]

        def _prepare(f: Frame) -> None:
            if before_export:
                before_export(f)

        meta = _fresh_export(
            page,
            target,
            md,
            task_hint,
            shell_path,
            hint,
            click_direct_export,
            prepare_frame=_prepare if before_export else None,
        )
        if not target.exists() or target.stat().st_size == 0:
            raise RuntimeError(f"导出文件无效: {target}")
        return url, frame.url, popups, meta
    if export_mode == "tms_scrape":
        url, iframe, popups = scrape_tms_inbound(page, target)
        return url, iframe, popups, None

    url = goto_shell(page, shell_path)
    frame = app_frame(page, path_hint=path_hint or shell_path.strip("/").split("/")[-1])
    popups = dismiss_interruptions(page, frame)
    hint = path_hint or shell_path.strip("/").split("/")[-1]

    def _prepare(f: Frame) -> None:
        if before_export:
            before_export(f)

    def _trigger(f: Frame) -> None:
        if "inventoryManage/product" in shell_path:
            trigger_inventory_custom_export(f)
        else:
            click_import_export(f)
            click_export_button(f)

    meta = _fresh_export(
        page,
        target,
        md,
        task_hint,
        shell_path,
        hint,
        _trigger,
        prepare_frame=_prepare if before_export else None,
    )
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"导出文件无效: {target}")
    return url, frame.url, popups, meta
