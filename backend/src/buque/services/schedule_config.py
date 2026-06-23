from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

DAILY_PIPELINE_HOUR = 6
DAILY_PIPELINE_MINUTE = 0


def daily_pipeline_trigger(tz: ZoneInfo) -> CronTrigger:
    return CronTrigger(
        hour=DAILY_PIPELINE_HOUR,
        minute=DAILY_PIPELINE_MINUTE,
        timezone=tz,
    )


def schedule_label() -> str:
    return f"每日 {DAILY_PIPELINE_HOUR:02d}:{DAILY_PIPELINE_MINUTE:02d}"


def next_scheduled_run(tz: ZoneInfo, *, now: datetime | None = None) -> datetime:
    current = now or datetime.now(tz)
    if current.tzinfo is None:
        current = current.replace(tzinfo=tz)
    candidate = current.replace(
        hour=DAILY_PIPELINE_HOUR,
        minute=DAILY_PIPELINE_MINUTE,
        second=0,
        microsecond=0,
    )
    if candidate <= current:
        candidate += timedelta(days=1)
    return candidate
