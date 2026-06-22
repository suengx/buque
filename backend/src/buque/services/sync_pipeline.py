from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Literal

from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.ingestion.erp_exporter import (
    ERP_SOURCES,
    ErpSyncResult,
    run_ingestion_from_erp,
    run_ingestion_from_files,
)
from buque.models.entities import IngestionRun, IngestionStatus
from buque.quality.checker import DataQualityChecker
from buque.schemas.api import PipelineRunResult
from buque.services.monitor_pipeline import run_event_pool_and_explain, run_rules

logger = logging.getLogger(__name__)
settings = get_settings()


def has_running_erp_sync(db: Session) -> bool:
    return (
        db.query(IngestionRun)
        .filter(
            IngestionRun.source.in_(ERP_SOURCES),
            IngestionRun.status == IngestionStatus.RUNNING,
        )
        .count()
        > 0
    )


def latest_ingestion_status(db: Session) -> list[IngestionRun]:
    runs: list[IngestionRun] = []
    for source in ERP_SOURCES:
        run = (
            db.query(IngestionRun)
            .filter(IngestionRun.source == source)
            .order_by(IngestionRun.id.desc())
            .first()
        )
        if run:
            runs.append(run)
    return runs


def run_erp_sync(db: Session, monitor_date: date) -> ErpSyncResult:
    if not settings.erp_base_url:
        raise RuntimeError("ERP_BASE_URL 未配置")
    return run_ingestion_from_erp(db, monitor_date)


def run_full_pipeline(
    db: Session,
    monitor_date: date,
    *,
    ingestion: Literal["erp", "fixtures"],
) -> PipelineRunResult:
    if ingestion == "fixtures":
        fixture_dir = Path(__file__).resolve().parents[3] / "fixtures" / "sample_exports"
        sync_result = run_ingestion_from_files(
            db,
            monitor_date,
            inventory_file=fixture_dir / "inventory.csv",
            orders_file=fixture_dir / "orders.csv",
            inbound_file=fixture_dir / "inbound.csv",
        )
    else:
        sync_result = run_erp_sync(db, monitor_date)

    issues = DataQualityChecker(db, monitor_date).run()
    results = run_rules(db, monitor_date)
    events, explained = run_event_pool_and_explain(db, monitor_date)
    return PipelineRunResult(
        monitor_date=monitor_date,
        ingestion=sync_result.ingestion_counts,
        quality_issues=len(issues),
        monitor_results=len(results),
        events=events,
        explained=explained,
    )


def run_erp_sync_with_optional_pipeline(
    db: Session,
    monitor_date: date,
    *,
    run_pipeline: bool,
) -> PipelineRunResult | ErpSyncResult:
    sync_result = run_erp_sync(db, monitor_date)
    if not run_pipeline:
        return sync_result
    issues = DataQualityChecker(db, monitor_date).run()
    results = run_rules(db, monitor_date)
    events, explained = run_event_pool_and_explain(db, monitor_date)
    return PipelineRunResult(
        monitor_date=monitor_date,
        ingestion=sync_result.ingestion_counts,
        quality_issues=len(issues),
        monitor_results=len(results),
        events=events,
        explained=explained,
    )
