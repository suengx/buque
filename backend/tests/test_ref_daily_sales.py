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
    RuleConfig,
)
from buque.services.ref_daily_sales import resolve_ref_daily_sales
from buque.services.rule_config import RuleConfigService


@pytest.fixture
def cfg_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    RuleConfig.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    for code, val, ptype in (
        ("BASE_SALES_PRIORITY", "ERP_7D_AVG", "string"),
        ("SALES_SPIKE_TRIM", "true", "bool"),
        ("SALES_SURGE_RATIO", "1.5", "float"),
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
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_resolve_ref_daily_sales_uses_erp_by_default(cfg_session: Session) -> None:
    cfg = RuleConfigService(cfg_session)
    ref, source, trimmed = resolve_ref_daily_sales(Decimal("8"), {}, cfg)
    assert ref == Decimal("8")
    assert source == "ERP_7D_AVG"
    assert trimmed is False


def test_resolve_ref_daily_sales_trims_spike(cfg_session: Session) -> None:
    cfg = RuleConfigService(cfg_session)
    metrics = {
        "sales_3d_avg": Decimal("15"),
        "sales_15d_avg": Decimal("8"),
    }
    ref, _, trimmed = resolve_ref_daily_sales(Decimal("12"), metrics, cfg)
    assert ref == Decimal("8")
    assert trimmed is True


def test_resolve_ref_daily_sales_rejects_unsupported_priority(cfg_session: Session) -> None:
    cfg_session.add(
        RuleConfig(
            rule_code="BASE_SALES_PRIORITY",
            rule_name="x",
            param_value="FORECAST_FIRST",
            param_type="string",
            is_enabled=True,
            version=2,
            effective_date=date(2026, 6, 22),
            proposer="test",
            change_reason="test",
        )
    )
    cfg_session.commit()
    cfg = RuleConfigService(cfg_session)
    ref, source, _ = resolve_ref_daily_sales(Decimal("5"), {}, cfg)
    assert ref is None
    assert source == "FORECAST_FIRST"
