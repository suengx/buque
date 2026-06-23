from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.schemas.api import OpsStatusResponse
from buque.services.erp_sync_job import build_pipeline_status, has_running_pipeline_job
from buque.services.schedule_config import next_scheduled_run, schedule_label


def build_ops_status(db: Session) -> OpsStatusResponse:
    settings = get_settings()
    tz = settings.tz
    status = build_pipeline_status(db)

    return OpsStatusResponse(
        timezone=settings.timezone,
        schedule_label=schedule_label(),
        next_scheduled_at=next_scheduled_run(tz),
        pipeline_active=has_running_pipeline_job(db),
        running_snapshot_id=status.snapshot_id if status.running else None,
        phase_message=status.phase_message if status.running else None,
        erp_configured=bool(settings.erp_base_url and settings.erp_username),
    )
