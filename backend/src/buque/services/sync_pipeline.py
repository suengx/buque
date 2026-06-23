from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Literal

from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.ingestion.erp_exporter import ErpSyncResult, run_ingestion_from_erp, run_ingestion_from_files
from buque.models.entities import ErpSyncPhase
from buque.schemas.api import PipelineRunResult
from buque.services.erp_sync_job import (
    append_log,
    finish_analysis_success,
    finish_job_failed,
    finish_sync_success,
    has_running_sync_job,
    update_job_phase,
)
from buque.services.monitor_pipeline import run_analysis_pipeline

logger = logging.getLogger(__name__)
settings = get_settings()

PhaseCallback = Callable[[ErpSyncPhase, str], None]


def has_running_erp_sync(db: Session) -> bool:
    return has_running_sync_job(db)


def _build_sync_summary(sync_result: ErpSyncResult, started_at, finished_at) -> dict:
    sources = {}
    for s in sync_result.sources:
        entry = {
            "status": s.status,
            "row_count": s.row_count,
            "file_path": s.file_path,
        }
        if s.transport_task_id:
            entry["transport_task_id"] = s.transport_task_id
        if s.transport_requested_at:
            entry["transport_requested_at"] = s.transport_requested_at
        if s.file_sha256:
            entry["file_sha256"] = s.file_sha256
        sources[s.source] = entry
    return {
        "sources": sources,
        "ingestion_counts": sync_result.ingestion_counts,
        "started_at": started_at.isoformat() if started_at else None,
        "finished_at": finished_at.isoformat() if finished_at else None,
    }


def run_sync_ingestion(
    db: Session,
    monitor_date: date,
    *,
    ingestion: Literal["erp", "fixtures"],
    on_phase: PhaseCallback | None = None,
) -> ErpSyncResult:
    if ingestion == "fixtures":
        fixture_dir = Path(__file__).resolve().parents[3] / "fixtures" / "sample_exports"
        if on_phase:
            on_phase(ErpSyncPhase.INGESTING, "正在写入样例数据…")
        return run_ingestion_from_files(
            db,
            monitor_date,
            inventory_file=fixture_dir / "inventory.csv",
            orders_file=fixture_dir / "orders.csv",
            inbound_file=fixture_dir / "inbound.csv",
        )

    if not settings.erp_base_url:
        raise RuntimeError("ERP_BASE_URL 未配置")

    def report(phase: ErpSyncPhase, message: str) -> None:
        if on_phase:
            on_phase(phase, message)

    return run_ingestion_from_erp(db, monitor_date, on_phase=report)


def run_sync_job(
    db: Session,
    monitor_date: date,
    job_id: int,
    *,
    ingestion: Literal["erp", "fixtures"] = "erp",
) -> ErpSyncResult:
    from buque.models.entities import ErpSyncJob, IngestionStatus

    job = db.get(ErpSyncJob, job_id)
    started_at = job.started_at if job else None

    def on_phase(phase: ErpSyncPhase, message: str) -> None:
        update_job_phase(db, job_id, phase, message)
        append_log(db, job_id, "INFO", message)

    try:
        sync_result = run_sync_ingestion(db, monitor_date, ingestion=ingestion, on_phase=on_phase)
        failed = [s for s in sync_result.sources if s.status != "SUCCESS"]
        if failed:
            errors = "; ".join(f"{s.source}: {s.error or s.status}" for s in failed)
            finish_job_failed(db, job_id, errors)
            raise RuntimeError(errors)

        finished_at = datetime_now()
        summary = _build_sync_summary(sync_result, started_at, finished_at)
        finish_sync_success(db, job_id, summary)
        return sync_result
    except Exception as exc:
        job = db.get(ErpSyncJob, job_id)
        if job and job.status == IngestionStatus.RUNNING:
            finish_job_failed(db, job_id, str(exc))
        raise


def run_analysis_job(db: Session, monitor_date: date, job_id: int) -> dict[str, int]:
    def on_progress(
        phase: ErpSyncPhase,
        message: str,
        current: int | None,
        total: int | None,
    ) -> None:
        update_job_phase(
            db,
            job_id,
            phase,
            message,
            progress_current=current,
            progress_total=total,
        )
        append_log(db, job_id, "INFO", message)

    try:
        summary = run_analysis_pipeline(db, monitor_date, on_progress=on_progress)
        finish_analysis_success(db, job_id, summary)
        return summary
    except Exception as exc:
        finish_job_failed(db, job_id, str(exc))
        raise


def run_full_pipeline(
    db: Session,
    monitor_date: date,
    *,
    ingestion: Literal["erp", "fixtures"],
) -> PipelineRunResult:
    sync_result = run_sync_ingestion(db, monitor_date, ingestion=ingestion)
    analysis = run_analysis_pipeline(db, monitor_date)
    return PipelineRunResult(
        monitor_date=monitor_date,
        ingestion=sync_result.ingestion_counts,
        quality_issues=analysis["quality_issues"],
        monitor_results=analysis["monitor_results"],
        events=analysis["events"],
        explained=analysis["explained"],
    )


def datetime_now():
    from datetime import datetime

    return datetime.now(settings.tz)
