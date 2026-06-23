from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from buque.models.entities import RuleConfig
from buque.services.rule_config import RuleConfigService
from buque.services.rule_config_admin import update_rule
from buque.services.rule_metric_labels import build_metric_labels


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    RuleConfig.__table__.create(engine, checkfirst=True)
    factory = sessionmaker(bind=engine)
    session = factory()
    for code, val, ptype in (
        ("DOS_RED_REG", "30", "int"),
        ("DOS_RED_SEA", "45", "int"),
        ("SLOW_DOS_RED_REG", "150", "int"),
        ("SLOW_DOS_RED_SEA", "180", "int"),
        ("STOCKOUT_ORANGE_FACTOR", "1.5", "float"),
        ("STOCKOUT_YELLOW_FACTOR", "2.0", "float"),
        ("SLOW_ORANGE_FACTOR", "0.85", "float"),
        ("SLOW_YELLOW_FACTOR", "0.7", "float"),
        ("SALES_SURGE_RATIO", "1.5", "float"),
        ("SALES_DROP_RATIO", "0.6", "float"),
        ("KEY_SKU_UPGRADE", "true", "bool"),
        ("INBOUND_RELIEF_DOWNGRADE", "true", "bool"),
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
                proposer="system",
                change_reason="seed",
            )
        )
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_metric_labels_reflect_dos_red_reg(db_session: Session) -> None:
    cfg = RuleConfigService(db_session)
    labels = build_metric_labels(cfg)
    red_labels = [x["label"] for x in labels["risk_levels"]["RED"]]
    assert "DOS≤30天" in red_labels

    update_rule(db_session, "DOS_RED_REG", "25", "测试")
    RuleConfigService(db_session).reload()
    labels2 = build_metric_labels(RuleConfigService(db_session))
    red_labels2 = [x["label"] for x in labels2["risk_levels"]["RED"]]
    assert "DOS≤25天" in red_labels2
