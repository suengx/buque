from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from buque.models.entities import (
    DimSku,
    ErpSyncJob,
    ErpSyncPhase,
    FactInventoryDaily,
    IngestionStatus,
    JobKind,
    MonitoringScope,
    RiskLevel,
    RiskType,
)
from buque.rules.engine import RuleEngine, _upgrade, _valid_sales


def test_upgrade_level() -> None:
    assert _upgrade(RiskLevel.GREEN, 1) == RiskLevel.YELLOW
    assert _upgrade(RiskLevel.RED, 1) == RiskLevel.RED


def test_dos_calculation() -> None:
    available = 25
    ref_daily = Decimal("8")
    dos = Decimal(available) / ref_daily
    assert dos == Decimal("3.125")


def test_valid_sales_rejects_nan() -> None:
    assert not _valid_sales(Decimal("NaN"))
    assert not _valid_sales(None)
    assert _valid_sales(Decimal("1.5"))


SNAPSHOT_ID = 1


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    for table in (ErpSyncJob.__table__, DimSku.__table__, FactInventoryDaily.__table__):
        table.create(engine, checkfirst=True)
    factory = sessionmaker(bind=engine)
    session = factory()
    session.add(
        ErpSyncJob(
            id=SNAPSHOT_ID,
            monitor_date=date(2026, 6, 22),
            job_kind=JobKind.PIPELINE,
            phase=ErpSyncPhase.DONE,
            status=IngestionStatus.SUCCESS,
        )
    )
    session.add(DimSku(sku="NAN-SKU", product_name="Test"))
    session.add(
        FactInventoryDaily(
            snapshot_id=SNAPSHOT_ID,
            date=date(2026, 6, 22),
            sku="NAN-SKU",
            warehouse="WH1",
            available_inventory=10,
            ref_daily_sales=Decimal("NaN"),
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_rule_engine_handles_nan_ref_daily_sales(db_session: Session) -> None:
    findings = RuleEngine(db_session, date(2026, 6, 22), SNAPSHOT_ID)._evaluate_warehouse_scope()
    anomaly = [f for f in findings if f.trigger_rule == "MISSING_DATA_BLOCK"]
    assert len(anomaly) == 1
    assert anomaly[0].risk_type == RiskType.DATA_ANOMALY
    assert anomaly[0].scope == MonitoringScope.WAREHOUSE
    assert anomaly[0].requires_explanation is False
