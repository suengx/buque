from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from buque.ingestion.parsers import (
    InventoryParser,
    OrdersParser,
    _normalize_inventory_row,
    _optional_decimal,
    _split_product_sku,
)
from buque.models.entities import (
    DimMskuMapping,
    DimSku,
    ErpSyncJob,
    ErpSyncPhase,
    FactInboundBatch,
    FactInventoryDaily,
    FactSalesDaily,
    IngestionRun,
    IngestionStatus,
    JobKind,
)

SNAPSHOT_ID = 1

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "gerpgo_samples"


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    for table in (
        ErpSyncJob.__table__,
        DimSku.__table__,
        DimMskuMapping.__table__,
        IngestionRun.__table__,
        FactInventoryDaily.__table__,
        FactSalesDaily.__table__,
        FactInboundBatch.__table__,
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
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_split_product_sku_newline() -> None:
    name, sku = _split_product_sku("COS沙发\nC0150515")
    assert name == "COS沙发"
    assert sku == "C0150515"


def test_normalize_inventory_row() -> None:
    import pandas as pd

    row = pd.Series({"sku": "COS沙发\nC0150515", "product_name": ""})
    sku, product_name = _normalize_inventory_row(row)
    assert sku == "C0150515"
    assert product_name == "COS沙发"


def test_optional_decimal_nan() -> None:
    from decimal import Decimal

    assert _optional_decimal(float("nan")) is None
    assert _optional_decimal(None) is None
    assert _optional_decimal("3.5") == Decimal("3.5")


def test_inventory_parser_nan_ref_sales(db_session: Session, tmp_path: Path) -> None:
    md = date(2026, 6, 22)
    csv = tmp_path / "inv_nan.csv"
    csv.write_text("sku,warehouse,available_inventory,ref_daily_sales\nNAN-SKU,WH1,10,\n", encoding="utf-8")
    InventoryParser(db_session, md, SNAPSHOT_ID).ingest_file(csv)
    row = (
        db_session.query(FactInventoryDaily)
        .filter(FactInventoryDaily.sku == "NAN-SKU")
        .one()
    )
    assert row.ref_daily_sales is None


def test_inventory_parser_gerpgo_sample(db_session: Session) -> None:
    md = date(2026, 6, 22)
    count = InventoryParser(db_session, md, SNAPSHOT_ID).ingest_file(FIXTURES / "inventory.csv")
    assert count == 2
    row = (
        db_session.query(FactInventoryDaily)
        .filter(FactInventoryDaily.sku == "C0150515")
        .one()
    )
    assert row.ref_daily_sales is not None
    assert db_session.get(DimSku, "C0150515") is not None


def test_orders_parser_multi_day(db_session: Session) -> None:
    md = date(2026, 6, 22)
    count = OrdersParser(db_session, md, SNAPSHOT_ID).ingest_file(FIXTURES / "orders.csv")
    assert count == 3
    dates = {r.date for r in db_session.query(FactSalesDaily).all()}
    assert dates == {date(2026, 6, 20), date(2026, 6, 21), date(2026, 6, 22)}
    amz = (
        db_session.query(FactSalesDaily)
        .filter(
            FactSalesDaily.msku == "MSKU-C0150515-AMZ",
            FactSalesDaily.date == date(2026, 6, 20),
        )
        .one()
    )
    assert amz.order_qty == 12
