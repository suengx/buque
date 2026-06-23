from datetime import date, datetime
from zoneinfo import ZoneInfo

from buque.ingestion.transport_center import (
    TransportTask,
    find_pending_task,
    parse_transport_row,
    select_download_task,
)

TZ = ZoneInfo("Asia/Shanghai")

INVENTORY_ROW = """000023955
仓库产品库存
已完成
~
手动
2026-06-08 19:06:07
含锁站点信息导出
2026-06-08 19:06:04
AI
下载"""

ORDERS_ROW = """000024281
全渠道销售订单
已完成
2026-05-24 ~ 2026-06-22
手动
2026-06-22 18:40:49
包含店铺:SUNBURY:US
2026-06-22 18:38:32
AI
下载"""

PROCESSING_ROW = """000024999
仓库产品库存
处理中
~
手动
2026-06-22 19:00:00
含锁站点信息导出
2026-06-22 19:00:01
AI
下载"""

CUSTOM_INVENTORY_ROW = """000024284
仓库产品库存-自定义导出
已完成
~
手动
2026-06-22 19:33:55
仓库产品库存数据导出
2026-06-22 19:33:56
AI
下载"""


def test_parse_inventory_row() -> None:
    task = parse_transport_row(INVENTORY_ROW, row_index=3, tz=TZ)
    assert task is not None
    assert task.task_id == "000023955"
    assert task.task_type == "仓库产品库存"
    assert task.status == "已完成"
    assert task.requested_at == datetime(2026, 6, 8, 19, 6, 7, tzinfo=TZ)
    assert task.row_index == 3


def test_parse_orders_row() -> None:
    task = parse_transport_row(ORDERS_ROW, tz=TZ)
    assert task is not None
    assert task.task_id == "000024281"
    assert task.requested_at.date() == date(2026, 6, 22)


def test_reject_stale_tasks() -> None:
    stale = parse_transport_row(INVENTORY_ROW, tz=TZ)
    assert stale is not None
    selected = select_download_task(
        [stale],
        hint="仓库产品库存",
        min_request_date=date(2026, 6, 22),
        before_task_ids=set(),
    )
    assert selected is None


def test_select_newest_fresh_task() -> None:
    older = TransportTask(
        task_id="000024280",
        task_type="全渠道销售订单",
        status="已完成",
        requested_at=datetime(2026, 6, 22, 14, 0, 0, tzinfo=TZ),
        row_index=0,
        raw_text="",
    )
    newer = TransportTask(
        task_id="000024281",
        task_type="全渠道销售订单",
        status="已完成",
        requested_at=datetime(2026, 6, 22, 18, 40, 49, tzinfo=TZ),
        row_index=1,
        raw_text="",
    )
    selected = select_download_task(
        [older, newer],
        hint="全渠道销售订单",
        min_request_date=date(2026, 6, 22),
        before_task_ids=set(),
    )
    assert selected is not None
    assert selected.task_id == "000024281"


def test_prefer_new_task_not_in_before_ids() -> None:
    old = parse_transport_row(INVENTORY_ROW, tz=TZ)
    fresh = TransportTask(
        task_id="000099999",
        task_type="仓库产品库存",
        status="已完成",
        requested_at=datetime(2026, 6, 22, 20, 0, 0, tzinfo=TZ),
        row_index=1,
        raw_text="",
    )
    assert old is not None
    selected = select_download_task(
        [old, fresh],
        hint="仓库产品库存",
        min_request_date=date(2026, 6, 22),
        before_task_ids={old.task_id},
    )
    assert selected is not None
    assert selected.task_id == "000099999"


def test_parse_custom_inventory_export_row() -> None:
    task = parse_transport_row(CUSTOM_INVENTORY_ROW, tz=TZ)
    assert task is not None
    assert task.task_id == "000024284"
    assert task.task_type == "仓库产品库存-自定义导出"
    assert task.requested_at == datetime(2026, 6, 22, 19, 33, 55, tzinfo=TZ)
    selected = select_download_task(
        [task],
        hint="仓库产品库存",
        min_request_date=date(2026, 6, 22),
        before_task_ids=set(),
    )
    assert selected is not None
    assert selected.task_id == "000024284"


def test_skip_processing_task() -> None:
    processing = parse_transport_row(PROCESSING_ROW, tz=TZ)
    assert processing is not None
    selected = select_download_task(
        [processing],
        hint="仓库产品库存",
        min_request_date=date(2026, 6, 22),
        before_task_ids=set(),
    )
    assert selected is None


def test_find_pending_processing_task() -> None:
    processing = parse_transport_row(PROCESSING_ROW, tz=TZ)
    assert processing is not None
    pending = find_pending_task(
        [processing],
        hint="仓库产品库存",
        min_request_date=date(2026, 6, 22),
        before_task_ids=set(),
    )
    assert pending is not None
    assert pending.task_id == "000024999"
    assert pending.status == "处理中"


def test_find_pending_excludes_before_ids() -> None:
    processing = parse_transport_row(PROCESSING_ROW, tz=TZ)
    assert processing is not None
    pending = find_pending_task(
        [processing],
        hint="仓库产品库存",
        min_request_date=date(2026, 6, 22),
        before_task_ids={"000024999"},
    )
    assert pending is None


def test_min_requested_at_filters_stale_completed() -> None:
    task = parse_transport_row(ORDERS_ROW, tz=TZ)
    assert task is not None
    cutoff = datetime(2026, 6, 22, 19, 0, 0, tzinfo=TZ)
    selected = select_download_task(
        [task],
        hint="全渠道销售订单",
        min_request_date=date(2026, 6, 22),
        before_task_ids=set(),
        min_requested_at=cutoff,
    )
    assert selected is None


def test_min_requested_at_accepts_fresh_completed() -> None:
    fresh = TransportTask(
        task_id="000024291",
        task_type="全渠道销售订单",
        status="已完成",
        requested_at=datetime(2026, 6, 23, 9, 23, 33, tzinfo=TZ),
        row_index=0,
        raw_text="",
    )
    cutoff = datetime(2026, 6, 23, 9, 20, 0, tzinfo=TZ)
    selected = select_download_task(
        [fresh],
        hint="全渠道销售订单",
        min_request_date=date(2026, 6, 22),
        before_task_ids={"000024288"},
        min_requested_at=cutoff,
    )
    assert selected is not None
    assert selected.task_id == "000024291"
