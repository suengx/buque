from datetime import datetime
from zoneinfo import ZoneInfo

from buque.services.schedule_config import next_scheduled_run, schedule_label


def test_schedule_label() -> None:
    assert schedule_label() == "每日 06:00"


def test_next_scheduled_run_same_day() -> None:
    tz = ZoneInfo("Asia/Shanghai")
    now = datetime(2026, 6, 23, 5, 30, tzinfo=tz)
    nxt = next_scheduled_run(tz, now=now)
    assert nxt.hour == 6
    assert nxt.minute == 0
    assert nxt.day == 23


def test_next_scheduled_run_next_day() -> None:
    tz = ZoneInfo("Asia/Shanghai")
    now = datetime(2026, 6, 23, 7, 0, tzinfo=tz)
    nxt = next_scheduled_run(tz, now=now)
    assert nxt.day == 24
    assert nxt.hour == 6
