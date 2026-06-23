from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TASK_ID_RE = re.compile(r"^(\d{6,})$")
DATETIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})")
COMPLETED_STATUSES = frozenset({"已完成", "完成"})
FAILED_STATUSES = frozenset({"失败"})
PROCESSING_STATUSES = frozenset({"处理中"})


@dataclass(frozen=True)
class TransportTask:
    task_id: str
    task_type: str
    status: str
    requested_at: datetime
    row_index: int
    raw_text: str


@dataclass(frozen=True)
class TransportTaskMeta:
    task_id: str
    requested_at: datetime
    task_type: str
    file_sha256: str


def _parse_status(lines: list[str]) -> str:
    for line in lines[1:6]:
        if line in COMPLETED_STATUSES or line in PROCESSING_STATUSES or line in FAILED_STATUSES:
            return line
        if "已完成" in line:
            return "已完成"
        if "处理中" in line:
            return "处理中"
        if "失败" in line:
            return "失败"
    return ""


def _parse_requested_at(lines: list[str]) -> datetime | None:
    manual_idx = next((i for i, line in enumerate(lines) if line == "手动"), None)
    if manual_idx is not None and manual_idx + 1 < len(lines):
        match = DATETIME_RE.search(lines[manual_idx + 1])
        if match:
            return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    for line in lines:
        match = DATETIME_RE.search(line)
        if match:
            return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    return None


def parse_transport_row(text: str, row_index: int = 0, tz: ZoneInfo | None = None) -> TransportTask | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    task_id_match = TASK_ID_RE.match(lines[0])
    if not task_id_match:
        return None
    task_type = lines[1] if len(lines) > 1 else ""
    status = _parse_status(lines)
    requested_at = _parse_requested_at(lines)
    if requested_at is None:
        return None
    if tz is not None:
        requested_at = requested_at.replace(tzinfo=tz)
    return TransportTask(
        task_id=task_id_match.group(1),
        task_type=task_type,
        status=status,
        requested_at=requested_at,
        row_index=row_index,
        raw_text=text,
    )


FRESHNESS_TOLERANCE = timedelta(seconds=5)


def _is_fresh_candidate(
    task: TransportTask,
    *,
    hint: str,
    min_request_date: date,
    before_task_ids: set[str],
    min_requested_at: datetime | None = None,
) -> bool:
    if hint not in task.task_type:
        return False
    if task.requested_at.date() < min_request_date:
        return False
    if task.task_id in before_task_ids:
        return False
    if min_requested_at is not None:
        cutoff = min_requested_at - FRESHNESS_TOLERANCE
        if task.requested_at < cutoff:
            return False
    return True


def find_pending_task(
    tasks: list[TransportTask],
    *,
    hint: str,
    min_request_date: date,
    before_task_ids: set[str],
    min_requested_at: datetime | None = None,
) -> TransportTask | None:
    """返回不在 before_ids 中的最新任务（处理中或已完成），用于轮询观测。"""
    candidates: list[TransportTask] = []
    for task in tasks:
        if not _is_fresh_candidate(
            task,
            hint=hint,
            min_request_date=min_request_date,
            before_task_ids=before_task_ids,
            min_requested_at=min_requested_at,
        ):
            continue
        if task.status not in PROCESSING_STATUSES | COMPLETED_STATUSES:
            continue
        candidates.append(task)
    if not candidates:
        return None
    return max(candidates, key=lambda t: t.requested_at)


def select_download_task(
    tasks: list[TransportTask],
    *,
    hint: str,
    min_request_date: date,
    before_task_ids: set[str],
    min_requested_at: datetime | None = None,
) -> TransportTask | None:
    candidates: list[TransportTask] = []
    for task in tasks:
        if not _is_fresh_candidate(
            task,
            hint=hint,
            min_request_date=min_request_date,
            before_task_ids=before_task_ids,
            min_requested_at=min_requested_at,
        ):
            continue
        if task.status not in COMPLETED_STATUSES:
            continue
        candidates.append(task)
    if not candidates:
        return None
    return max(candidates, key=lambda t: t.requested_at)


def file_sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
