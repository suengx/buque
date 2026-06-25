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
    FactSalesDaily,
    IngestionStatus,
    JobKind,
    MonitoringScope,
    RiskLevel,
    RiskType,
    RuleConfig,
)
from buque.rules.engine import RuleEngine, _upgrade, _valid_sales
from buque.services.rule_config import RuleConfigService


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
    for table in (
        ErpSyncJob.__table__,
        DimSku.__table__,
        FactInventoryDaily.__table__,
        FactSalesDaily.__table__,
        RuleConfig.__table__,
    ):
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
    session.add(
        RuleConfig(
            rule_code="BASE_SALES_PRIORITY",
            rule_name="BASE_SALES_PRIORITY",
            param_value="ERP_7D_AVG",
            param_type="string",
            is_enabled=True,
            version=1,
            effective_date=date(2026, 6, 22),
            proposer="test",
            change_reason="test",
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
    assert anomaly[0].risk_level == RiskLevel.GREEN


def test_stockout_orange_factor_from_config(db_session: Session) -> None:
    bind = db_session.get_bind()
    RuleConfig.__table__.create(bind, checkfirst=True)
    FactSalesDaily.__table__.create(bind, checkfirst=True)
    rules = (
        ("DOS_RED_REG", "30", "int"),
        ("DOS_RED_SEA", "45", "int"),
        ("SLOW_DOS_RED_REG", "150", "int"),
        ("SLOW_DOS_RED_SEA", "180", "int"),
        ("STOCKOUT_ORANGE_FACTOR", "2.0", "float"),
        ("STOCKOUT_YELLOW_FACTOR", "2.0", "float"),
        ("SLOW_ORANGE_FACTOR", "0.85", "float"),
        ("SLOW_YELLOW_FACTOR", "0.7", "float"),
        ("SALES_SURGE_RATIO", "1.5", "float"),
        ("SALES_SPIKE_TRIM", "false", "bool"),
        ("KEY_SKU_UPGRADE", "false", "bool"),
        ("INBOUND_RELIEF_DOWNGRADE", "false", "bool"),
    )
    for code, val, ptype in rules:
        db_session.add(
            RuleConfig(
                rule_code=code,
                rule_name=code,
                param_value=val,
                param_type=ptype,
                is_enabled=True,
                version=1,
                effective_date=date(2026, 6, 22),
                proposer="test",
                change_reason="test",
            )
        )
    db_session.add(DimSku(sku="SKU-A", product_name="A"))
    db_session.add(
        FactInventoryDaily(
            snapshot_id=SNAPSHOT_ID,
            date=date(2026, 6, 22),
            sku="SKU-A",
            warehouse="WH1",
            available_inventory=100,
            ref_daily_sales=Decimal("2"),
        )
    )
    db_session.commit()
    cfg = RuleConfigService(db_session)
    findings = RuleEngine(db_session, date(2026, 6, 22), SNAPSHOT_ID, cfg=cfg)._evaluate_warehouse_scope()
    stockout = [f for f in findings if f.risk_type == RiskType.STOCKOUT]
    assert len(stockout) == 1
    assert stockout[0].risk_level == RiskLevel.ORANGE
