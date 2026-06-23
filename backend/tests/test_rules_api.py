from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from buque.db import get_db
from buque.main import create_app
from buque.models.entities import RuleConfig
from buque.services.rule_config_seed import RULE_CONFIG_SEED, SEED_EFFECTIVE_DATE


@pytest.fixture
def client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    RuleConfig.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    for item in RULE_CONFIG_SEED:
        session.add(
            RuleConfig(
                rule_code=item["rule_code"],
                rule_name=item["rule_name"],
                param_value=item["param_value"],
                param_type=item["param_type"],
                is_enabled=True,
                version=1,
                effective_date=SEED_EFFECTIVE_DATE,
                proposer="system",
                change_reason="seed",
            )
        )
    session.commit()

    app = create_app()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    session.close()


def test_list_rules_grouped(client: TestClient) -> None:
    res = client.get("/api/v1/rules")
    assert res.status_code == 200
    data = res.json()
    assert len(data["groups"]) >= 5
    codes = {r["rule_code"] for g in data["groups"] for r in g["rules"]}
    assert "DOS_RED_REG" in codes


def test_metric_labels_endpoint(client: TestClient) -> None:
    res = client.get("/api/v1/rules/metric-labels")
    assert res.status_code == 200
    data = res.json()
    assert "DOS≤30天" in [x["label"] for x in data["risk_levels"]["RED"]]


def test_update_rule(client: TestClient) -> None:
    res = client.put(
        "/api/v1/rules/DOS_RED_REG",
        json={"param_value": "32", "change_reason": "api test"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["version"] == 2
    assert body["param_value"] == "32"

    labels = client.get("/api/v1/rules/metric-labels").json()
    assert "DOS≤32天" in [x["label"] for x in labels["risk_levels"]["RED"]]
