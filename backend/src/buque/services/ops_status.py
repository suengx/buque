from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.schemas.api import OpsStatusResponse
from buque.services.erp_sync_job import (
    build_analysis_status,
    build_sync_latest,
    build_sync_status,
)
from buque.services.schedule_config import next_scheduled_run, schedule_label


def build_ops_status(db: Session, monitor_date: date) -> OpsStatusResponse:
    settings = get_settings()
    tz = settings.tz
    sync_status = build_sync_status(db, monitor_date)
    analysis_status = build_analysis_status(db, monitor_date)
    latest = build_sync_latest(db, monitor_date)

    sync_running = sync_status.running
    analysis_running = analysis_status.running

    return OpsStatusResponse(
        monitor_date=monitor_date,
        timezone=settings.timezone,
        schedule_label=schedule_label(),
        next_scheduled_at=next_scheduled_run(tz),
        pipeline_active=sync_running or analysis_running,
        sync_running=sync_running,
        analysis_running=analysis_running,
        sync_phase_message=sync_status.phase_message if sync_running else None,
        analysis_phase_message=analysis_status.phase_message if analysis_running else None,
        erp_configured=bool(settings.erp_base_url and settings.erp_username),
        latest_sync=latest,
    )
