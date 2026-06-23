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
    AnalysisStatusResponse,
    ErpSyncLatestResponse,
    ErpSyncLogEntry,
    ErpSyncStatusResponse,
    IngestionSourceStatus,
)

settings = get_settings()
LOG_TAIL = 50


def create_sync_job(db: Session, monitor_date: date) -> ErpSyncJob:
    job = ErpSyncJob(
        monitor_date=monitor_date,
        job_kind=JobKind.SYNC,
        phase=ErpSyncPhase.EXPORTING,
        status=IngestionStatus.RUNNING,
        phase_message="正在登录积加 ERP…",
        started_at=datetime.now(settings.tz),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    append_log(db, job.id, "INFO", "同步任务已启动")
    return job


def create_analysis_job(db: Session, monitor_date: date) -> ErpSyncJob:
    job = ErpSyncJob(
        monitor_date=monitor_date,
        job_kind=JobKind.ANALYSIS,
        phase=ErpSyncPhase.QUALITY,
        status=IngestionStatus.RUNNING,
        phase_message="数据质量检查…",
        started_at=datetime.now(settings.tz),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    append_log(db, job.id, "INFO", "分析任务已启动")
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


def finish_sync_success(db: Session, job_id: int, sync_summary: dict) -> None:
    job = db.get(ErpSyncJob, job_id)
    if not job:
        return
    job.phase = ErpSyncPhase.DONE
    job.status = IngestionStatus.SUCCESS
    job.phase_message = "同步完成"
    job.sync_summary = sync_summary
    job.finished_at = datetime.now(settings.tz)
    db.commit()
    append_log(db, job_id, "INFO", "同步完成")


def finish_analysis_success(db: Session, job_id: int, analysis_summary: dict) -> None:
    job = db.get(ErpSyncJob, job_id)
    if not job:
        return
    job.phase = ErpSyncPhase.DONE
    job.status = IngestionStatus.SUCCESS
    job.phase_message = "分析完成"
    job.analysis_summary = analysis_summary
    job.finished_at = datetime.now(settings.tz)
    db.commit()
    append_log(db, job_id, "INFO", "分析完成")


def finish_job_failed(db: Session, job_id: int, error: str) -> None:
    job = db.get(ErpSyncJob, job_id)
    if not job:
        return
    job.status = IngestionStatus.FAILED
    job.error_message = error
    job.phase_message = "任务失败"
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


def reconcile_stale_jobs(db: Session, kind: JobKind) -> int:
    now = datetime.now(settings.tz)
    cutoff = now - timedelta(seconds=settings.erp_job_stale_seconds)
    activity_cutoff = now - timedelta(seconds=settings.erp_job_stale_buffer_seconds * 2)
    running_jobs = (
        db.query(ErpSyncJob)
        .filter(
            ErpSyncJob.job_kind == kind,
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


def has_running_sync_job(db: Session) -> bool:
    reconcile_stale_jobs(db, JobKind.SYNC)
    return _has_running_job(db, JobKind.SYNC)


def has_running_analysis_job(db: Session) -> bool:
    reconcile_stale_jobs(db, JobKind.ANALYSIS)
    return _has_running_job(db, JobKind.ANALYSIS)


def _has_running_job(db: Session, kind: JobKind) -> bool:
    return (
        db.query(ErpSyncJob)
        .filter(
            ErpSyncJob.job_kind == kind,
            ErpSyncJob.status == IngestionStatus.RUNNING,
        )
        .count()
        > 0
    )


def get_job(db: Session, job_id: int | None, monitor_date: date, kind: JobKind) -> ErpSyncJob | None:
    if job_id is not None:
        job = db.get(ErpSyncJob, job_id)
        if job and job.job_kind == kind:
            return job
        return None

    running = (
        db.query(ErpSyncJob)
        .filter(
            ErpSyncJob.monitor_date == monitor_date,
            ErpSyncJob.job_kind == kind,
            ErpSyncJob.status == IngestionStatus.RUNNING,
        )
        .order_by(ErpSyncJob.id.desc())
        .first()
    )
    if running:
        return running

    return (
        db.query(ErpSyncJob)
        .filter(ErpSyncJob.monitor_date == monitor_date, ErpSyncJob.job_kind == kind)
        .order_by(ErpSyncJob.id.desc())
        .first()
    )


def get_latest_successful_sync(db: Session, monitor_date: date) -> ErpSyncJob | None:
    return (
        db.query(ErpSyncJob)
        .filter(
            ErpSyncJob.monitor_date == monitor_date,
            ErpSyncJob.job_kind == JobKind.SYNC,
            ErpSyncJob.status == IngestionStatus.SUCCESS,
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
        ErpSyncLogEntry(
            level=r.level,
            message=r.message,
            created_at=r.created_at,
        )
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


def build_sync_status(
    db: Session,
    monitor_date: date,
    job_id: int | None = None,
) -> ErpSyncStatusResponse:
    reconcile_stale_jobs(db, JobKind.SYNC)
    job = get_job(db, job_id, monitor_date, JobKind.SYNC)
    if not job:
        sources = [
            IngestionSourceStatus(source=source, status="PENDING", row_count=0)
            for source in ERP_SOURCES
        ]
        return ErpSyncStatusResponse(
            monitor_date=monitor_date,
            running=False,
            job_id=None,
            job_status="PENDING",
            phase=None,
            phase_message=None,
            error=None,
            finished_at=None,
            sync_summary=None,
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

    return ErpSyncStatusResponse(
        monitor_date=monitor_date,
        running=running,
        job_id=job.id,
        job_status=job.status.value,
        phase=job.phase.value,
        phase_message=job.phase_message,
        error=job.error_message,
        finished_at=job.finished_at,
        sync_summary=job.sync_summary,
        logs=_job_logs(db, job.id),
        sources=sources,
    )


def build_analysis_status(
    db: Session,
    monitor_date: date,
    job_id: int | None = None,
) -> AnalysisStatusResponse:
    reconcile_stale_jobs(db, JobKind.ANALYSIS)
    job = get_job(db, job_id, monitor_date, JobKind.ANALYSIS)
    if not job:
        return AnalysisStatusResponse(
            monitor_date=monitor_date,
            running=False,
            job_id=None,
            job_status="PENDING",
            phase=None,
            phase_message=None,
            error=None,
            finished_at=None,
            progress_current=None,
            progress_total=None,
            analysis_summary=None,
            logs=[],
        )

    return AnalysisStatusResponse(
        monitor_date=monitor_date,
        running=job.status == IngestionStatus.RUNNING,
        job_id=job.id,
        job_status=job.status.value,
        phase=job.phase.value,
        phase_message=job.phase_message,
        error=job.error_message,
        finished_at=job.finished_at,
        progress_current=job.progress_current,
        progress_total=job.progress_total,
        analysis_summary=job.analysis_summary,
        logs=_job_logs(db, job.id),
    )


def build_sync_latest(db: Session, monitor_date: date) -> ErpSyncLatestResponse:
    job = get_latest_successful_sync(db, monitor_date)
    if not job:
        return ErpSyncLatestResponse(monitor_date=monitor_date, has_sync=False)
    return ErpSyncLatestResponse(
        monitor_date=monitor_date,
        has_sync=True,
        job_id=job.id,
        finished_at=job.finished_at,
        sync_summary=job.sync_summary,
    )
