from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from buque.api.deps import auth_router_dependencies
from buque.config import get_settings
from buque.db import SessionLocal, get_db
from buque.schemas.api import (
    OpsStatusResponse,
    PipelineAccepted,
    PipelineRequest,
    PipelineRunResult,
    PipelineStatusResponse,
    SnapshotSummary,
)
from buque.services.erp_sync_job import (
    build_pipeline_status,
    create_pipeline_job,
    has_running_pipeline_job,
    list_snapshots,
    to_pipeline_accepted,
)
from buque.services.ops_status import build_ops_status
from buque.services.sync_pipeline import run_full_pipeline, run_pipeline_job

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=auth_router_dependencies(),
)


def _run_pipeline_background(monitor_date: date, job_id: int) -> None:
    db = SessionLocal()
    try:
        run_pipeline_job(db, monitor_date, job_id, ingestion="erp")
        logger.info("流水线完成: %s snapshot=%s", monitor_date, job_id)
    except Exception:
        logger.exception("流水线失败: %s snapshot=%s", monitor_date, job_id)
    finally:
        db.close()


@router.post("/pipeline/start", response_model=PipelineAccepted, status_code=status.HTTP_202_ACCEPTED)
def start_pipeline(
    body: PipelineRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> PipelineAccepted:
    if not settings.erp_base_url or not settings.erp_username:
        raise HTTPException(status_code=400, detail="ERP 未配置")
    if has_running_pipeline_job(db):
        raise HTTPException(status_code=409, detail="已有流水线任务进行中")
    md = body.monitor_date or date.today()
    job = create_pipeline_job(db, md)
    background_tasks.add_task(_run_pipeline_background, md, job.id)
    return to_pipeline_accepted(job)


@router.get("/pipeline/status", response_model=PipelineStatusResponse)
def pipeline_status(
    job_id: int | None = None,
    db: Session = Depends(get_db),
) -> PipelineStatusResponse:
    return build_pipeline_status(db, job_id)


@router.get("/snapshots", response_model=list[SnapshotSummary])
def snapshots(db: Session = Depends(get_db)) -> list[SnapshotSummary]:
    return list_snapshots(db)


@router.get("/ops/status", response_model=OpsStatusResponse)
def ops_status(db: Session = Depends(get_db)) -> OpsStatusResponse:
    return build_ops_status(db)


@router.post("/pipeline/run", response_model=PipelineRunResult)
def run_pipeline(
    monitor_date: date | None = None,
    use_fixtures: bool = True,
    ingestion_source: str | None = None,
    db: Session = Depends(get_db),
) -> PipelineRunResult:
    md = monitor_date or date.today()
    if ingestion_source == "erp":
        return run_full_pipeline(db, md, ingestion="erp")
    if ingestion_source == "fixtures" or use_fixtures:
        return run_full_pipeline(db, md, ingestion="fixtures")
    return run_full_pipeline(db, md, ingestion="erp")
