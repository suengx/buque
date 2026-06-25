from datetime import date

import pytest
from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import Session, sessionmaker

from buque.models.entities import (
    DimSku,
    ErpSyncJob,
    ErpSyncPhase,
    FactMonitorResult,
    IngestionStatus,
    JobKind,
    MonitoringScope,
    RiskLevel,
    RiskType,
)
from buque.services.risk_aggregation import data_anomaly_count, level_counts

SNAPSHOT_ID = 1


@pytest.fixture
def db_session() -> Session:
    FactMonitorResult.__table__.c.trigger_metrics.type = JSON()
    engine = create_engine("sqlite:///:memory:")
    for table in (
        ErpSyncJob.__table__,
        DimSku.__table__,
        FactMonitorResult.__table__,
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
    session.add(DimSku(sku="SKU-A", product_name="A"))
    session.add(DimSku(sku="SKU-B", product_name="B"))
    session.add(
        FactMonitorResult(
            snapshot_id=SNAPSHOT_ID,
            date=date(2026, 6, 22),
            sku="SKU-A",
            warehouse="WH1",
            scope=MonitoringScope.WAREHOUSE,
            risk_type=RiskType.DATA_ANOMALY,
            risk_level=RiskLevel.ORANGE,
            trigger_rule="MISSING_DATA_BLOCK",
            trigger_metrics={},
        )
    )
    session.add(
        FactMonitorResult(
            snapshot_id=SNAPSHOT_ID,
            date=date(2026, 6, 22),
            sku="SKU-B",
            warehouse="WH1",
            scope=MonitoringScope.WAREHOUSE,
            risk_type=RiskType.STOCKOUT,
            risk_level=RiskLevel.ORANGE,
            trigger_rule="DOS_STOCKOUT",
            trigger_metrics={},
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_level_counts_excludes_data_anomaly(db_session: Session) -> None:
    counts = level_counts(db_session, SNAPSHOT_ID)
    assert counts[RiskLevel.ORANGE.value] == 1
    assert sum(counts.values()) == 1


def test_data_anomaly_count(db_session: Session) -> None:
    assert data_anomaly_count(db_session, SNAPSHOT_ID) == 1


# alias import used by routes
def test_count_data_anomalies_alias(db_session: Session) -> None:
    from buque.services.risk_aggregation import data_anomaly_count as count_data_anomalies

    assert count_data_anomalies(db_session, SNAPSHOT_ID) == 1
