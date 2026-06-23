from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.db import SessionLocal, get_db
from buque.schemas.api import (
    AnalysisAccepted,
    AnalysisRequest,
    AnalysisStatusResponse,
    ErpSyncAccepted,
    ErpSyncLatestResponse,
    ErpSyncRequest,
    ErpSyncStatusResponse,
    OpsStatusResponse,
    PipelineRunResult,
)
from buque.services.erp_sync_job import (
    build_analysis_status,
    build_sync_latest,
    build_sync_status,
    create_analysis_job,
    create_sync_job,
    has_running_analysis_job,
    has_running_sync_job,
)
from buque.services.ops_status import build_ops_status
from buque.services.sync_pipeline import run_analysis_job, run_full_pipeline, run_sync_job

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _run_sync_background(monitor_date: date, job_id: int) -> None:
    db = SessionLocal()
    try:
        run_sync_job(db, monitor_date, job_id, ingestion="erp")
        logger.info("ERP 同步完成: %s job=%s", monitor_date, job_id)
    except Exception:
        logger.exception("ERP 同步失败: %s job=%s", monitor_date, job_id)
    finally:
        db.close()


def _run_analysis_background(monitor_date: date, job_id: int) -> None:
    db = SessionLocal()
    try:
        run_analysis_job(db, monitor_date, job_id)
        logger.info("分析完成: %s job=%s", monitor_date, job_id)
    except Exception:
        logger.exception("分析失败: %s job=%s", monitor_date, job_id)
    finally:
        db.close()


@router.post("/sync/erp", response_model=ErpSyncAccepted, status_code=status.HTTP_202_ACCEPTED)
def start_erp_sync(
    body: ErpSyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ErpSyncAccepted:
    if not settings.erp_base_url or not settings.erp_username:
        raise HTTPException(status_code=400, detail="ERP 未配置")
    if has_running_sync_job(db):
        raise HTTPException(status_code=409, detail="已有 ERP 同步任务进行中")
    md = body.monitor_date or date.today()
    job = create_sync_job(db, md)
    background_tasks.add_task(_run_sync_background, md, job.id)
    return ErpSyncAccepted(monitor_date=md, job_id=job.id)


@router.get("/sync/status", response_model=ErpSyncStatusResponse)
def erp_sync_status(
    monitor_date: date | None = None,
    job_id: int | None = None,
    db: Session = Depends(get_db),
) -> ErpSyncStatusResponse:
    md = monitor_date or date.today()
    return build_sync_status(db, md, job_id=job_id)


@router.get("/ops/status", response_model=OpsStatusResponse)
def ops_status(
    monitor_date: date | None = None,
    db: Session = Depends(get_db),
) -> OpsStatusResponse:
    md = monitor_date or date.today()
    return build_ops_status(db, md)


@router.get("/sync/latest", response_model=ErpSyncLatestResponse)
def erp_sync_latest(
    monitor_date: date | None = None,
    db: Session = Depends(get_db),
) -> ErpSyncLatestResponse:
    md = monitor_date or date.today()
    return build_sync_latest(db, md)


@router.post("/analyze", response_model=AnalysisAccepted, status_code=status.HTTP_202_ACCEPTED)
def start_analysis(
    body: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> AnalysisAccepted:
    if has_running_analysis_job(db):
        raise HTTPException(status_code=409, detail="已有分析任务进行中")
    md = body.monitor_date or date.today()
    job = create_analysis_job(db, md)
    background_tasks.add_task(_run_analysis_background, md, job.id)
    return AnalysisAccepted(monitor_date=md, job_id=job.id)


@router.get("/analyze/status", response_model=AnalysisStatusResponse)
def analysis_status(
    monitor_date: date | None = None,
    job_id: int | None = None,
    db: Session = Depends(get_db),
) -> AnalysisStatusResponse:
    md = monitor_date or date.today()
    return build_analysis_status(db, md, job_id=job_id)


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
