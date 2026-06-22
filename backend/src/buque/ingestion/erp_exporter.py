from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from buque.ingestion.gerpgo_session import GerpgGoSession
from buque.ingestion.parsers import InboundParser, InventoryParser, OrdersParser
from buque.services.rule_config import RuleConfigService

ERP_SOURCES = ("erp_inventory", "erp_orders", "tms_inbound")


@dataclass
class SourceSyncResult:
    source: str
    status: str
    row_count: int = 0
    file_path: str | None = None
    error: str | None = None
    ingestion_run_id: int | None = None


@dataclass
class ErpSyncResult:
    monitor_date: date
    sources: list[SourceSyncResult] = field(default_factory=list)

    @property
    def ingestion_counts(self) -> dict[str, int]:
        return {
            s.source.replace("erp_", "").replace("tms_", ""): s.row_count
            for s in self.sources
            if s.status == "SUCCESS"
        }


def _ingest_safe(
    db: Session,
    source: str,
    ingest_fn,
) -> SourceSyncResult:
    from buque.models.entities import IngestionRun, IngestionStatus

    db.rollback()
    try:
        row_count = ingest_fn()
        run = (
            db.query(IngestionRun)
            .filter(IngestionRun.source == source)
            .order_by(IngestionRun.id.desc())
            .first()
        )
        return SourceSyncResult(
            source=source,
            status="SUCCESS",
            row_count=row_count,
            file_path=run.file_path if run else None,
            ingestion_run_id=run.id if run else None,
        )
    except Exception as exc:
        db.rollback()
        run = (
            db.query(IngestionRun)
            .filter(IngestionRun.source == source)
            .order_by(IngestionRun.id.desc())
            .first()
        )
        status = run.status.value if run and run.status else IngestionStatus.FAILED.value
        return SourceSyncResult(
            source=source,
            status=status,
            row_count=0,
            file_path=run.file_path if run else None,
            error=str(exc),
            ingestion_run_id=run.id if run else None,
        )


def run_ingestion_from_files(
    db: Session,
    monitor_date: date,
    inventory_file: Path | None = None,
    orders_file: Path | None = None,
    inbound_file: Path | None = None,
) -> ErpSyncResult:
    rule_config = RuleConfigService(db)
    result = ErpSyncResult(monitor_date=monitor_date)

    if inventory_file and inventory_file.exists():
        result.sources.append(
            _ingest_safe(
                db,
                "erp_inventory",
                lambda: InventoryParser(db, monitor_date).ingest_file(inventory_file),
            )
        )
    if orders_file and orders_file.exists():
        result.sources.append(
            _ingest_safe(
                db,
                "erp_orders",
                lambda: OrdersParser(db, monitor_date).ingest_file(orders_file),
            )
        )
    if inbound_file and inbound_file.exists():
        result.sources.append(
            _ingest_safe(
                db,
                "tms_inbound",
                lambda: InboundParser(db, monitor_date, rule_config).ingest_file(inbound_file),
            )
        )
    return result


def run_ingestion_from_erp(db: Session, monitor_date: date) -> ErpSyncResult:
    with GerpgGoSession() as session:
        inventory_path = session.export_inventory_merged(monitor_date)
        orders_path = session.export_orders(monitor_date)
        inbound_path = session.export_tms_inbound(monitor_date)

    return run_ingestion_from_files(
        db,
        monitor_date,
        inventory_file=inventory_path,
        orders_file=orders_path,
        inbound_file=inbound_path,
    )
