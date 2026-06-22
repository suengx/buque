from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.db import SessionLocal, get_db
from buque.ingestion.erp_exporter import ERP_SOURCES
from buque.schemas.api import (
    ErpSyncAccepted,
    ErpSyncRequest,
    ErpSyncStatusResponse,
    IngestionSourceStatus,
    PipelineRunResult,
)
from buque.services.sync_pipeline import (
    has_running_erp_sync,
    latest_ingestion_status,
    run_erp_sync_with_optional_pipeline,
    run_full_pipeline,
)

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _run_sync_background(monitor_date: date, run_pipeline: bool) -> None:
    db = SessionLocal()
    try:
        run_erp_sync_with_optional_pipeline(db, monitor_date, run_pipeline=run_pipeline)
        logger.info("ERP 同步完成: %s pipeline=%s", monitor_date, run_pipeline)
    except Exception:
        logger.exception("ERP 同步失败: %s", monitor_date)
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
    if has_running_erp_sync(db):
        raise HTTPException(status_code=409, detail="已有 ERP 同步任务进行中")
    md = body.monitor_date or date.today()
    background_tasks.add_task(_run_sync_background, md, body.run_pipeline)
    return ErpSyncAccepted(monitor_date=md)


@router.get("/sync/status", response_model=ErpSyncStatusResponse)
def erp_sync_status(
    monitor_date: date | None = None,
    db: Session = Depends(get_db),
) -> ErpSyncStatusResponse:
    md = monitor_date or date.today()
    runs = latest_ingestion_status(db)
    running = has_running_erp_sync(db)
    sources: list[IngestionSourceStatus] = []
    seen = {r.source for r in runs}
    for run in runs:
        sources.append(
            IngestionSourceStatus(
                source=run.source,
                status=run.status.value,
                row_count=run.row_count,
                file_path=run.file_path,
                error=run.error_message,
                finished_at=run.finished_at,
                ingestion_run_id=run.id,
            )
        )
    for source in ERP_SOURCES:
        if source not in seen:
            sources.append(
                IngestionSourceStatus(
                    source=source,
                    status="PENDING",
                    row_count=0,
                )
            )
    return ErpSyncStatusResponse(monitor_date=md, running=running, sources=sources)


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
