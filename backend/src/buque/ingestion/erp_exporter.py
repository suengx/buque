from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from collections.abc import Callable

from sqlalchemy.orm import Session

from buque.ingestion.gerpgo_session import GerpgGoSession
from buque.ingestion.parsers import InboundParser, InventoryParser, OrdersParser
from buque.models.entities import ErpSyncPhase
from buque.services.rule_config import RuleConfigService

ERP_SOURCES = ("erp_inventory", "erp_orders", "tms_inbound")

PhaseCallback = Callable[[ErpSyncPhase, str], None]


@dataclass
class SourceSyncResult:
    source: str
    status: str
    row_count: int = 0
    file_path: str | None = None
    error: str | None = None
    ingestion_run_id: int | None = None
    transport_task_id: str | None = None
    transport_requested_at: str | None = None
    file_sha256: str | None = None


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
    snapshot_id: int,
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
                lambda: InventoryParser(db, monitor_date, snapshot_id).ingest_file(inventory_file),
            )
        )
    if orders_file and orders_file.exists():
        result.sources.append(
            _ingest_safe(
                db,
                "erp_orders",
                lambda: OrdersParser(db, monitor_date, snapshot_id).ingest_file(orders_file),
            )
        )
    if inbound_file and inbound_file.exists():
        result.sources.append(
            _ingest_safe(
                db,
                "tms_inbound",
                lambda: InboundParser(db, monitor_date, snapshot_id, rule_config).ingest_file(
                    inbound_file
                ),
            )
        )
    return result


def _attach_transport_meta(result: ErpSyncResult, metas: dict) -> None:
    from buque.ingestion.transport_center import TransportTaskMeta

    mapping = {
        "erp_inventory": metas.get("erp_inventory"),
        "erp_orders": metas.get("erp_orders"),
    }
    for source in result.sources:
        meta: TransportTaskMeta | None = mapping.get(source.source)
        if meta is None:
            continue
        source.transport_task_id = meta.task_id
        source.transport_requested_at = meta.requested_at.isoformat()
        source.file_sha256 = meta.file_sha256


def run_ingestion_from_erp(
    db: Session,
    monitor_date: date,
    snapshot_id: int,
    on_phase: PhaseCallback | None = None,
) -> ErpSyncResult:
    def report(phase: ErpSyncPhase, message: str) -> None:
        if on_phase:
            on_phase(phase, message)

    report(ErpSyncPhase.EXPORTING, "正在导出产品库存…")
    with GerpgGoSession() as session:
        inventory_path = session.export_inventory_merged(monitor_date)
        report(ErpSyncPhase.EXPORTING, "正在导出全渠道订单…")
        orders_path = session.export_orders(
            monitor_date,
            on_status=lambda msg: report(ErpSyncPhase.EXPORTING, msg),
        )
        report(ErpSyncPhase.EXPORTING, "正在抓取 TMS 在途…")
        inbound_path = session.export_tms_inbound(monitor_date)
        transport_metas = dict(session.transport_metas)

    report(ErpSyncPhase.INGESTING, "正在写入数据库…")
    result = run_ingestion_from_files(
        db,
        monitor_date,
        snapshot_id,
        inventory_file=inventory_path,
        orders_file=orders_path,
        inbound_file=inbound_path,
    )
    _attach_transport_meta(result, transport_metas)
    return result
