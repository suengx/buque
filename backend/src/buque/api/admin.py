from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from buque.db import get_db
from buque.ingestion.erp_exporter import run_ingestion_from_files
from buque.quality.checker import DataQualityChecker
from buque.schemas.api import PipelineRunResult
from buque.services.monitor_pipeline import run_event_pool_and_explain, run_rules

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/pipeline/run", response_model=PipelineRunResult)
def run_pipeline(
    monitor_date: date | None = None,
    use_fixtures: bool = True,
    db: Session = Depends(get_db),
) -> PipelineRunResult:
    md = monitor_date or date.today()
    fixture_dir = Path(__file__).resolve().parents[3] / "fixtures" / "sample_exports"
    ingestion: dict[str, int] = {}
    if use_fixtures and fixture_dir.exists():
        ingestion = run_ingestion_from_files(
            db,
            md,
            inventory_file=fixture_dir / "inventory.csv",
            orders_file=fixture_dir / "orders.csv",
            inbound_file=fixture_dir / "inbound.csv",
        )
    issues = DataQualityChecker(db, md).run()
    results = run_rules(db, md)
    events, explained = run_event_pool_and_explain(db, md)
    return PipelineRunResult(
        monitor_date=md,
        ingestion=ingestion,
        quality_issues=len(issues),
        monitor_results=len(results),
        events=events,
        explained=explained,
    )
