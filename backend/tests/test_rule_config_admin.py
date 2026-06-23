from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from buque.models.entities import RuleConfig
from buque.services.rule_config import RuleConfigService
from buque.services.rule_config_admin import (
    RuleConfigValidationError,
    get_effective_rule,
    list_effective_rules,
    update_rule,
)


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    RuleConfig.__table__.create(engine, checkfirst=True)
    factory = sessionmaker(bind=engine)
    session = factory()
    session.add(
        RuleConfig(
            rule_code="DOS_RED_REG",
            rule_name="常规品断货红灯",
            param_value="30",
            param_type="int",
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


def test_update_rule_increments_version(db_session: Session) -> None:
    row = update_rule(db_session, "DOS_RED_REG", "对齐业务口径", param_value="35")
    assert row.version == 2
    assert row.param_value == "35"
    effective = list_effective_rules(db_session)
    assert len(effective) == 1
    assert effective[0].param_value == "35"
    cfg = RuleConfigService(db_session)
    assert cfg.get_int("DOS_RED_REG") == 35


def test_update_rule_requires_change_reason(db_session: Session) -> None:
    with pytest.raises(RuleConfigValidationError):
        update_rule(db_session, "DOS_RED_REG", "  ", param_value="35")


def test_update_rule_validates_dos_range(db_session: Session) -> None:
    with pytest.raises(RuleConfigValidationError):
        update_rule(db_session, "DOS_RED_REG", "test", param_value="999")


def test_get_effective_rule_returns_latest(db_session: Session) -> None:
    update_rule(db_session, "DOS_RED_REG", "调低阈值", param_value="28")
    current = get_effective_rule(db_session, "DOS_RED_REG")
    assert current is not None
    assert current.version == 2


def test_update_rule_toggles_is_enabled(db_session: Session) -> None:
    row = update_rule(db_session, "DOS_RED_REG", "暂停该规则", is_enabled=False)
    assert row.is_enabled is False
    assert row.version == 2
    assert get_effective_rule(db_session, "DOS_RED_REG") is None
    from buque.services.rule_config_admin import list_admin_rules

    admin = list_admin_rules(db_session)
    assert len(admin) == 1
    assert admin[0].is_enabled is False


def test_update_rule_rejects_no_change(db_session: Session) -> None:
    with pytest.raises(RuleConfigValidationError, match="未检测到变更"):
        update_rule(db_session, "DOS_RED_REG", "noop")
