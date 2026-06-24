from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from buque.config import get_settings
from buque.db import get_db
from buque.main import create_app
from buque.models.entities import RuleConfig, User
from buque.services.rule_config_seed import RULE_CONFIG_SEED, SEED_EFFECTIVE_DATE


@pytest.fixture
def auth_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_PASSWORD_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    session = factory()

    app = create_app()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    session.close()
    get_settings.cache_clear()


def test_register_login_and_me(auth_client: TestClient) -> None:
    register = auth_client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert register.status_code == 200
    body = register.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "user@example.com"
    token = body["access_token"]

    me = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_invalid_jwt_returns_401(auth_client: TestClient) -> None:
    res = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert res.status_code == 401


def test_protected_api_requires_auth(auth_client: TestClient) -> None:
    res = auth_client.get("/api/v1/health")
    assert res.status_code == 200
    res = auth_client.get("/api/v1/reports/daily")
    assert res.status_code == 401


def test_google_login_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    app = create_app()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    mock_info = {
        "sub": "google-sub-123",
        "email": "google@example.com",
        "name": "Google User",
        "picture": "https://example.com/avatar.png",
    }
    with patch("buque.services.auth.id_token.verify_oauth2_token", return_value=mock_info):
        res = client.post(
            "/api/v1/auth/google",
            json={"credential": "fake-google-credential"},
        )
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "google@example.com"
    session.close()
    get_settings.cache_clear()


def test_auth_required_false_allows_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    get_settings.cache_clear()

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
    client = TestClient(app)
    res = client.get("/api/v1/rules")
    assert res.status_code == 200
    session.close()
    get_settings.cache_clear()
