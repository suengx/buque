from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.ingestion.erp_exporter import ERP_SOURCES
from buque.models.entities import (
    ErpSyncJob,
    ErpSyncLog,
    ErpSyncPhase,
    IngestionRun,
    IngestionStatus,
    JobKind,
)
from buque.schemas.api import (
    ErpSyncLogEntry,
    IngestionSourceStatus,
    PipelineAccepted,
    PipelineStatusResponse,
    SnapshotSummary,
)

settings = get_settings()
LOG_TAIL = 50


def create_pipeline_job(db: Session, monitor_date: date) -> ErpSyncJob:
    job = ErpSyncJob(
        monitor_date=monitor_date,
        job_kind=JobKind.PIPELINE,
        phase=ErpSyncPhase.EXPORTING,
        status=IngestionStatus.RUNNING,
        phase_message="正在登录积加 ERP…",
        started_at=datetime.now(settings.tz),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    append_log(db, job.id, "INFO", "流水线已启动")
    return job


def append_log(db: Session, job_id: int, level: str, message: str) -> None:
    db.add(
        ErpSyncLog(
            job_id=job_id,
            level=level,
            message=message,
            created_at=datetime.now(settings.tz),
        )
    )
    db.commit()


def update_job_phase(
    db: Session,
    job_id: int,
    phase: ErpSyncPhase,
    message: str,
    *,
    progress_current: int | None = None,
    progress_total: int | None = None,
) -> None:
    job = db.get(ErpSyncJob, job_id)
    if not job or job.status != IngestionStatus.RUNNING:
        return
    job.phase = phase
    job.phase_message = message
    if progress_current is not None:
        job.progress_current = progress_current
    if progress_total is not None:
        job.progress_total = progress_total
    db.commit()


def finish_pipeline_success(
    db: Session,
    job_id: int,
    sync_summary: dict,
    analysis_summary: dict,
) -> None:
    job = db.get(ErpSyncJob, job_id)
    if not job:
        return
    job.phase = ErpSyncPhase.DONE
    job.status = IngestionStatus.SUCCESS
    job.phase_message = "同步并分析完成"
    job.sync_summary = sync_summary
    job.analysis_summary = analysis_summary
    job.finished_at = datetime.now(settings.tz)
    db.commit()
    append_log(db, job_id, "INFO", "流水线完成")


def finish_job_failed(db: Session, job_id: int, error: str) -> None:
    job = db.get(ErpSyncJob, job_id)
    if not job:
        return
    job.status = IngestionStatus.FAILED
    job.error_message = error
    job.phase_message = "流水线失败"
    job.finished_at = datetime.now(settings.tz)
    db.commit()
    append_log(db, job_id, "ERROR", error)


def _job_started_at(job: ErpSyncJob) -> datetime:
    started = job.started_at or datetime.now(settings.tz)
    if started.tzinfo is None:
        return started.replace(tzinfo=settings.tz)
    return started.astimezone(settings.tz)


def _last_log_at(db: Session, job_id: int) -> datetime | None:
    log = (
        db.query(ErpSyncLog)
        .filter(ErpSyncLog.job_id == job_id)
        .order_by(ErpSyncLog.id.desc())
        .first()
    )
    if log is None or log.created_at is None:
        return None
    created = log.created_at
    if created.tzinfo is None:
        return created.replace(tzinfo=settings.tz)
    return created.astimezone(settings.tz)


def reconcile_stale_jobs(db: Session) -> int:
    now = datetime.now(settings.tz)
    cutoff = now - timedelta(seconds=settings.erp_job_stale_seconds)
    activity_cutoff = now - timedelta(seconds=settings.erp_job_stale_buffer_seconds * 2)
    running_jobs = (
        db.query(ErpSyncJob)
        .filter(
            ErpSyncJob.job_kind == JobKind.PIPELINE,
            ErpSyncJob.status == IngestionStatus.RUNNING,
        )
        .all()
    )
    stale_jobs: list[ErpSyncJob] = []
    for job in running_jobs:
        if _job_started_at(job) >= cutoff:
            continue
        last_log = _last_log_at(db, job.id)
        if last_log is not None and last_log >= activity_cutoff:
            continue
        stale_jobs.append(job)
    for job in stale_jobs:
        finish_job_failed(db, job.id, "任务超时或进程中断，已自动释放")
    return len(stale_jobs)


def has_running_pipeline_job(db: Session) -> bool:
    reconcile_stale_jobs(db)
    return (
        db.query(ErpSyncJob)
        .filter(
            ErpSyncJob.job_kind == JobKind.PIPELINE,
            ErpSyncJob.status == IngestionStatus.RUNNING,
        )
        .count()
        > 0
    )


def get_pipeline_job(db: Session, job_id: int | None) -> ErpSyncJob | None:
    if job_id is not None:
        job = db.get(ErpSyncJob, job_id)
        if job and job.job_kind == JobKind.PIPELINE:
            return job
        return None
    return (
        db.query(ErpSyncJob)
        .filter(
            ErpSyncJob.job_kind == JobKind.PIPELINE,
            ErpSyncJob.status == IngestionStatus.RUNNING,
        )
        .order_by(ErpSyncJob.id.desc())
        .first()
    )


def _job_logs(db: Session, job_id: int) -> list[ErpSyncLogEntry]:
    rows = (
        db.query(ErpSyncLog)
        .filter(ErpSyncLog.job_id == job_id)
        .order_by(ErpSyncLog.id.desc())
        .limit(LOG_TAIL)
        .all()
    )
    return [
        ErpSyncLogEntry(level=r.level, message=r.message, created_at=r.created_at)
        for r in reversed(rows)
    ]


def _ingestion_runs_for_job(db: Session, job: ErpSyncJob) -> dict[str, IngestionRun]:
    runs: dict[str, IngestionRun] = {}
    for source in ERP_SOURCES:
        run = (
            db.query(IngestionRun)
            .filter(
                IngestionRun.source == source,
                IngestionRun.started_at >= job.started_at,
            )
            .order_by(IngestionRun.id.desc())
            .first()
        )
        if run:
            runs[source] = run
    return runs


def build_pipeline_status(db: Session, job_id: int | None = None) -> PipelineStatusResponse:
    reconcile_stale_jobs(db)
    job = get_pipeline_job(db, job_id)
    if not job:
        sources = [
            IngestionSourceStatus(source=source, status="PENDING", row_count=0)
            for source in ERP_SOURCES
        ]
        return PipelineStatusResponse(
            snapshot_id=None,
            monitor_date=date.today(),
            running=False,
            job_status="PENDING",
            phase=None,
            phase_message=None,
            error=None,
            finished_at=None,
            sync_summary=None,
            analysis_summary=None,
            progress_current=None,
            progress_total=None,
            logs=[],
            sources=sources,
        )

    running = job.status == IngestionStatus.RUNNING
    job_runs = _ingestion_runs_for_job(db, job) if job.phase != ErpSyncPhase.EXPORTING else {}
    sources: list[IngestionSourceStatus] = []

    for source in ERP_SOURCES:
        if job.status == IngestionStatus.RUNNING and job.phase == ErpSyncPhase.EXPORTING:
            sources.append(IngestionSourceStatus(source=source, status="EXPORTING", row_count=0))
            continue
        run = job_runs.get(source)
        if run:
            sources.append(
                IngestionSourceStatus(
                    source=source,
                    status=run.status.value,
                    row_count=run.row_count,
                    file_path=run.file_path,
                    error=run.error_message,
                    finished_at=run.finished_at,
                    ingestion_run_id=run.id,
                )
            )
        elif job.status == IngestionStatus.RUNNING:
            sources.append(IngestionSourceStatus(source=source, status="INGESTING", row_count=0))
        else:
            sources.append(IngestionSourceStatus(source=source, status="PENDING", row_count=0))

    return PipelineStatusResponse(
        snapshot_id=job.id,
        monitor_date=job.monitor_date,
        running=running,
        job_status=job.status.value,
        phase=job.phase.value,
        phase_message=job.phase_message,
        error=job.error_message,
        finished_at=job.finished_at,
        sync_summary=job.sync_summary,
        analysis_summary=job.analysis_summary,
        progress_current=job.progress_current,
        progress_total=job.progress_total,
        logs=_job_logs(db, job.id),
        sources=sources,
    )


def list_snapshots(db: Session) -> list[SnapshotSummary]:
    rows = (
        db.query(ErpSyncJob)
        .filter(
            ErpSyncJob.job_kind == JobKind.PIPELINE,
            ErpSyncJob.status == IngestionStatus.SUCCESS,
        )
        .order_by(ErpSyncJob.finished_at.desc(), ErpSyncJob.id.desc())
        .all()
    )
    return [
        SnapshotSummary(
            id=job.id,
            monitor_date=job.monitor_date,
            finished_at=job.finished_at,
            sync_summary=job.sync_summary,
            analysis_summary=job.analysis_summary,
        )
        for job in rows
    ]


def to_pipeline_accepted(job: ErpSyncJob) -> PipelineAccepted:
    return PipelineAccepted(
        snapshot_id=job.id,
        monitor_date=job.monitor_date,
        message="同步并分析已启动",
    )
