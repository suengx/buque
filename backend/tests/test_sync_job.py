from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from buque.config import get_settings
from buque.models.entities import (
    ErpSyncJob,
    ErpSyncLog,
    ErpSyncPhase,
    IngestionRun,
    IngestionStatus,
    JobKind,
    MonitoringScope,
    RiskLevel,
    RiskType,
)
from buque.services.erp_sync_job import (
    append_log,
    build_analysis_status,
    build_sync_latest,
    build_sync_status,
    create_analysis_job,
    create_sync_job,
    finish_analysis_success,
    finish_job_failed,
    finish_sync_success,
    has_running_analysis_job,
    has_running_sync_job,
    reconcile_stale_jobs,
    update_job_phase,
)
from buque.services.monitor_pipeline import MonitorPersistence


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    for table in (
        ErpSyncJob.__table__,
        ErpSyncLog.__table__,
        IngestionRun.__table__,
    ):
        table.create(engine, checkfirst=True)
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def test_sync_job_lifecycle(db_session: Session) -> None:
    md = date(2026, 6, 22)
    job = create_sync_job(db_session, md)
    assert job.job_kind == JobKind.SYNC
    assert has_running_sync_job(db_session)
    update_job_phase(db_session, job.id, ErpSyncPhase.EXPORTING, "正在导出…")
    status = build_sync_status(db_session, md, job_id=job.id)
    assert status.running is True
    assert status.phase == "EXPORTING"
    assert all(s.status == "EXPORTING" for s in status.sources)
    finish_sync_success(db_session, job.id, {"ingestion_counts": {"inventory": 10}})
    status = build_sync_status(db_session, md, job_id=job.id)
    assert status.job_status == "SUCCESS"
    assert status.running is False
    assert status.sync_summary["ingestion_counts"]["inventory"] == 10
    assert not has_running_sync_job(db_session)


def test_sync_job_failed(db_session: Session) -> None:
    md = date(2026, 6, 22)
    job = create_sync_job(db_session, md)
    finish_job_failed(db_session, job.id, "规则引擎错误")
    status = build_sync_status(db_session, md, job_id=job.id)
    assert status.job_status == "FAILED"
    assert status.error == "规则引擎错误"


def test_sync_status_uses_job_scoped_ingestion(db_session: Session) -> None:
    md = date(2026, 6, 22)
    job = create_sync_job(db_session, md)
    settings = get_settings()
    started = datetime.now(settings.tz)
    db_session.add(
        IngestionRun(
            source="erp_inventory",
            status=IngestionStatus.SUCCESS,
            row_count=100,
            started_at=started,
            finished_at=started,
        )
    )
    db_session.commit()
    update_job_phase(db_session, job.id, ErpSyncPhase.INGESTING, "落库中")
    status = build_sync_status(db_session, md, job_id=job.id)
    inv = next(s for s in status.sources if s.source == "erp_inventory")
    assert inv.status == "SUCCESS"
    assert inv.row_count == 100


def test_analysis_job_lifecycle(db_session: Session) -> None:
    md = date(2026, 6, 22)
    job = create_analysis_job(db_session, md)
    assert job.job_kind == JobKind.ANALYSIS
    assert has_running_analysis_job(db_session)
    update_job_phase(db_session, job.id, ErpSyncPhase.RULES, "规则计算…")
    status = build_analysis_status(db_session, md, job_id=job.id)
    assert status.phase == "RULES"
    finish_analysis_success(db_session, job.id, {"events": 5, "explained": 5})
    status = build_analysis_status(db_session, md, job_id=job.id)
    assert status.job_status == "SUCCESS"
    assert status.analysis_summary["events"] == 5


def test_sync_and_analysis_jobs_independent(db_session: Session) -> None:
    md = date(2026, 6, 22)
    create_sync_job(db_session, md)
    create_analysis_job(db_session, md)
    assert has_running_sync_job(db_session)
    assert has_running_analysis_job(db_session)


def test_append_log_and_latest(db_session: Session) -> None:
    md = date(2026, 6, 22)
    job = create_sync_job(db_session, md)
    append_log(db_session, job.id, "INFO", "导出库存完成")
    finish_sync_success(db_session, job.id, {"ingestion_counts": {"inventory": 1}})
    latest = build_sync_latest(db_session, md)
    assert latest.has_sync is True
    status = build_sync_status(db_session, md, job_id=job.id)
    assert any("导出库存完成" in log.message for log in status.logs)


def test_build_event_pool_excludes_data_anomaly() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.delete = MagicMock()
    md = date(2026, 6, 22)
    persistence = MonitorPersistence(db, md)

    anomaly = MagicMock()
    anomaly.requires_explanation = True
    anomaly.risk_type = RiskType.DATA_ANOMALY
    anomaly.scope = MonitoringScope.WAREHOUSE
    anomaly.date = md
    anomaly.sku = "SKU1"
    anomaly.warehouse = "WH1"
    anomaly.risk_level = RiskLevel.ORANGE
    anomaly.trigger_rule = "MISSING_DATA_BLOCK"
    anomaly.trigger_metrics = {}
    anomaly.requires_human_confirm = False
    anomaly.dos = None
    anomaly.ref_daily_sales = None
    anomaly.available_inventory = 0
    anomaly.relief_note = None
    anomaly.id = 1

    stockout = MagicMock()
    stockout.requires_explanation = True
    stockout.risk_type = RiskType.STOCKOUT
    stockout.scope = MonitoringScope.WAREHOUSE
    stockout.date = md
    stockout.sku = "SKU2"
    stockout.warehouse = "WH1"
    stockout.risk_level = RiskLevel.RED
    stockout.trigger_rule = "STOCKOUT_RED"
    stockout.trigger_metrics = {}
    stockout.requires_human_confirm = True
    stockout.dos = None
    stockout.ref_daily_sales = None
    stockout.available_inventory = 0
    stockout.relief_note = None
    stockout.id = 2

    events = persistence.build_event_pool([anomaly, stockout])
    assert len(events) == 1
    assert events[0].risk_type == RiskType.STOCKOUT
    assert db.add.call_count == 1


def test_build_event_pool_excludes_orange_sales_anomaly() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.delete = MagicMock()
    md = date(2026, 6, 22)
    persistence = MonitorPersistence(db, md)

    sales_orange = MagicMock()
    sales_orange.requires_explanation = True
    sales_orange.risk_type = RiskType.SALES_ANOMALY
    sales_orange.scope = MonitoringScope.WAREHOUSE
    sales_orange.date = md
    sales_orange.sku = "SKU3"
    sales_orange.warehouse = "WH1"
    sales_orange.risk_level = RiskLevel.ORANGE
    sales_orange.trigger_rule = "SALES_SURGE"
    sales_orange.trigger_metrics = {}
    sales_orange.requires_human_confirm = False
    sales_orange.dos = None
    sales_orange.ref_daily_sales = None
    sales_orange.available_inventory = 100
    sales_orange.relief_note = None
    sales_orange.id = 3

    events = persistence.build_event_pool([sales_orange])
    assert len(events) == 0
    assert db.add.call_count == 0


def test_reconcile_stale_jobs(db_session: Session) -> None:
    md = date(2026, 6, 22)
    job = create_sync_job(db_session, md)
    settings = get_settings()
    stale_time = datetime.now(settings.tz) - timedelta(seconds=settings.erp_job_stale_seconds + 60)
    job.started_at = stale_time
    for log in db_session.query(ErpSyncLog).filter(ErpSyncLog.job_id == job.id):
        log.created_at = stale_time
    db_session.commit()
    assert reconcile_stale_jobs(db_session, JobKind.SYNC) == 1
    assert not has_running_sync_job(db_session)
    status = build_sync_status(db_session, md, job_id=job.id)
    assert status.job_status == "FAILED"
    assert "自动释放" in (status.error or "")


def test_reconcile_skips_job_with_recent_log(db_session: Session) -> None:
    md = date(2026, 6, 22)
    job = create_sync_job(db_session, md)
    settings = get_settings()
    job.started_at = datetime.now(settings.tz) - timedelta(seconds=settings.erp_job_stale_seconds + 60)
    db_session.commit()
    append_log(db_session, job.id, "INFO", "轮询传输中心等待新任务…")
    assert reconcile_stale_jobs(db_session, JobKind.SYNC) == 0
    assert has_running_sync_job(db_session)


def test_status_prefers_running_job_without_job_id(db_session: Session) -> None:
    md = date(2026, 6, 22)
    job = create_sync_job(db_session, md)
    finish_sync_success(db_session, job.id, {"ingestion_counts": {"inventory": 1}})
    running = create_sync_job(db_session, md)
    status = build_sync_status(db_session, md)
    assert status.running is True
    assert status.job_id == running.id
