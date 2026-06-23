from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from buque.models.entities import ErpSyncJob, IngestionStatus, JobKind


def resolve_snapshot_id(db: Session, snapshot_id: int | None) -> int:
    if snapshot_id is not None:
        job = db.get(ErpSyncJob, snapshot_id)
        if not job or job.job_kind != JobKind.PIPELINE or job.status != IngestionStatus.SUCCESS:
            raise HTTPException(status_code=404, detail="快照不存在或未完成")
        return job.id
    default = default_snapshot_id(db)
    if default is None:
        raise HTTPException(status_code=404, detail="暂无可用快照")
    return default


def get_snapshot(db: Session, snapshot_id: int) -> ErpSyncJob:
    job = db.get(ErpSyncJob, snapshot_id)
    if not job or job.job_kind != JobKind.PIPELINE:
        raise HTTPException(status_code=404, detail="快照不存在")
    return job


def default_snapshot_id(db: Session) -> int | None:
    job = (
        db.query(ErpSyncJob)
        .filter(
            ErpSyncJob.job_kind == JobKind.PIPELINE,
            ErpSyncJob.status == IngestionStatus.SUCCESS,
        )
        .order_by(ErpSyncJob.finished_at.desc(), ErpSyncJob.id.desc())
        .first()
    )
    return job.id if job else None


def latest_snapshot_for_date(db: Session, business_date: date) -> ErpSyncJob | None:
    return (
        db.query(ErpSyncJob)
        .filter(
            ErpSyncJob.job_kind == JobKind.PIPELINE,
            ErpSyncJob.status == IngestionStatus.SUCCESS,
            ErpSyncJob.monitor_date == business_date,
        )
        .order_by(ErpSyncJob.finished_at.desc(), ErpSyncJob.id.desc())
        .first()
    )


def previous_snapshot(db: Session, snapshot_id: int) -> ErpSyncJob | None:
    job = get_snapshot(db, snapshot_id)
    if job.finished_at is None:
        return None
    return (
        db.query(ErpSyncJob)
        .filter(
            ErpSyncJob.job_kind == JobKind.PIPELINE,
            ErpSyncJob.status == IngestionStatus.SUCCESS,
            ErpSyncJob.id != snapshot_id,
            (
                (ErpSyncJob.finished_at < job.finished_at)
                | ((ErpSyncJob.finished_at == job.finished_at) & (ErpSyncJob.id < job.id))
            ),
        )
        .order_by(ErpSyncJob.finished_at.desc(), ErpSyncJob.id.desc())
        .first()
    )
