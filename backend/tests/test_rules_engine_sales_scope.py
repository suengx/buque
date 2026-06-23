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
    RuleConfig,
)
from buque.rules.engine import RuleEngine
from buque.services.rule_config import RuleConfigService

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
    session = sessionmaker(bind=engine)()
    session.add(
        ErpSyncJob(
            id=SNAPSHOT_ID,
            monitor_date=date(2026, 6, 22),
            job_kind=JobKind.PIPELINE,
            phase=ErpSyncPhase.DONE,
            status=IngestionStatus.SUCCESS,
        )
    )
    for code, val, ptype in (
        ("BASE_SALES_PRIORITY", "ERP_7D_AVG", "string"),
        ("DOS_RED_REG", "30", "int"),
        ("DOS_RED_SEA", "45", "int"),
        ("SLOW_DOS_RED_REG", "150", "int"),
        ("SLOW_DOS_RED_SEA", "180", "int"),
        ("STOCKOUT_ORANGE_FACTOR", "1.5", "float"),
        ("STOCKOUT_YELLOW_FACTOR", "2.0", "float"),
        ("SLOW_ORANGE_FACTOR", "0.85", "float"),
        ("SLOW_YELLOW_FACTOR", "0.7", "float"),
        ("SALES_SURGE_RATIO", "1.5", "float"),
        ("SALES_SPIKE_TRIM", "false", "bool"),
        ("KEY_SKU_UPGRADE", "false", "bool"),
        ("INBOUND_RELIEF_DOWNGRADE", "false", "bool"),
    ):
        session.add(
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
    session.add(DimSku(sku="SKU-A", product_name="A"))
    session.add(
        FactInventoryDaily(
            snapshot_id=SNAPSHOT_ID,
            date=date(2026, 6, 22),
            sku="SKU-A",
            warehouse="WH1",
            available_inventory=0,
            ref_daily_sales=Decimal("2"),
        )
    )
    session.add(
        FactSalesDaily(
            snapshot_id=SNAPSHOT_ID,
            date=date(2026, 6, 20),
            msku="M1",
            channel="Amazon",
            sku="SKU-A",
            warehouse="WH1",
            order_qty=10,
        )
    )
    session.add(
        FactSalesDaily(
            snapshot_id=SNAPSHOT_ID,
            date=date(2026, 6, 21),
            msku="M1",
            channel="Amazon",
            sku="SKU-A",
            warehouse="WH1",
            order_qty=10,
        )
    )
    session.add(
        FactSalesDaily(
            snapshot_id=SNAPSHOT_ID,
            date=date(2026, 6, 22),
            msku="M1",
            channel="Amazon",
            sku="SKU-A",
            warehouse="WH1",
            order_qty=10,
        )
    )
    session.add(
        FactSalesDaily(
            snapshot_id=SNAPSHOT_ID,
            date=date(2026, 6, 22),
            msku="M1",
            channel="Wayfair",
            sku="SKU-A",
            warehouse="WH2",
            order_qty=99,
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_sales_metrics_scoped_to_warehouse(db_session: Session) -> None:
    engine = RuleEngine(
        db_session, date(2026, 6, 22), SNAPSHOT_ID, cfg=RuleConfigService(db_session)
    )
    wh1 = engine._sales_metrics("SKU-A", "WH1", MonitoringScope.WAREHOUSE)
    assert wh1["sales_3d_avg"] == Decimal("10")

    findings = engine._evaluate_warehouse_scope()
    stockout = [f for f in findings if f.trigger_rule == "DOS_STOCKOUT"]
    assert len(stockout) == 1
    m = stockout[0].trigger_metrics
    assert m["available_inventory"] == 0
    assert m["erp_ref_daily_sales"] == 2.0
    assert m["ref_daily_sales"] == 2.0
    assert m["ref_sales_source"] == "ERP_7D_AVG"
    assert m["sales_3d_avg"] == 10.0
    j = m["judgment"]
    assert j["kind"] == "stockout_dos"
    assert j["base_level"] == "RED"
    assert j["final_level"] == "RED"
    assert j["modifiers"] == []
