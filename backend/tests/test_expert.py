from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from buque.config import get_settings
from buque.db import get_db
from buque.main import create_app
from buque.models.entities import (
    ChatMessage,
    ChatSession,
    ErpSyncJob,
    ErpSyncPhase,
    FactAgentExplain,
    FactMonitorResult,
    IngestionStatus,
    JobKind,
    MonitoringScope,
    RiskLevel,
    RiskType,
    User,
)
from buque.services.auth import hash_password
from buque.services.expert_agent import StreamEventOut
from buque.services.expert_service import adopt_explanation_draft


@pytest.fixture
def expert_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, sessionmaker]:
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (User, ErpSyncJob, ChatSession, ChatMessage):
        table.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    session = factory()

    user = User(email="expert@example.com", password_hash=hash_password("password123"))
    session.add(user)
    job = ErpSyncJob(
        id=1,
        monitor_date=date(2026, 6, 23),
        job_kind=JobKind.PIPELINE,
        status=IngestionStatus.SUCCESS,
        phase=ErpSyncPhase.DONE,
    )
    session.add(job)
    session.commit()

    app = create_app()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "expert@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})

    yield client, factory
    session.close()
    get_settings.cache_clear()


async def _fake_stream(db, session, user_content):
    del db, session, user_content
    yield StreamEventOut("delta", {"text": "分析完成"})
    yield StreamEventOut("done", {"message_id": 1})


def test_create_session_and_isolation(expert_client) -> None:
    client, factory = expert_client
    created = client.post(
        "/api/v1/expert/sessions",
        json={"snapshot_id": 1, "sku": "SKU-001", "warehouse": "WH-A"},
    )
    assert created.status_code == 200
    session_id = created.json()["id"]

    detail = client.get(f"/api/v1/expert/sessions/{session_id}")
    assert detail.status_code == 200
    assert detail.json()["sku"] == "SKU-001"

    session = factory()
    other = User(email="other@example.com", password_hash=hash_password("password123"))
    session.add(other)
    session.commit()

    app = create_app()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    other_client = TestClient(app)
    login = other_client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "password123"},
    )
    other_client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
    denied = other_client.get(f"/api/v1/expert/sessions/{session_id}")
    assert denied.status_code == 404
    session.close()


def test_list_sessions_filters_by_snapshot(expert_client) -> None:
    client, factory = expert_client
    db = factory()
    job2 = ErpSyncJob(
        id=2,
        monitor_date=date(2026, 6, 24),
        job_kind=JobKind.PIPELINE,
        status=IngestionStatus.SUCCESS,
        phase=ErpSyncPhase.DONE,
    )
    db.add(job2)
    user = db.query(User).filter(User.email == "expert@example.com").one()
    db.add(ChatSession(user_id=user.id, snapshot_id=1, title="snap-1"))
    db.add(ChatSession(user_id=user.id, snapshot_id=2, title="snap-2"))
    db.commit()

    all_rows = client.get("/api/v1/expert/sessions")
    assert all_rows.status_code == 200
    assert len(all_rows.json()) == 2

    snap1 = client.get("/api/v1/expert/sessions", params={"snapshot_id": 1})
    assert snap1.status_code == 200
    titles = [row["title"] for row in snap1.json()]
    assert titles == ["snap-1"]

    snap2 = client.get("/api/v1/expert/sessions", params={"snapshot_id": 2})
    assert snap2.status_code == 200
    assert [row["title"] for row in snap2.json()] == ["snap-2"]
    db.close()


@patch("buque.api.expert.stream_agent_turn", new=_fake_stream)
def test_send_message_sse(expert_client) -> None:
    client, _factory = expert_client
    created = client.post(
        "/api/v1/expert/sessions",
        json={"snapshot_id": 1, "sku": "SKU-001"},
    )
    session_id = created.json()["id"]

    with client.stream(
        "POST",
        f"/api/v1/expert/sessions/{session_id}/messages",
        json={"content": "请分析"},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
        assert "event: delta" in body


def test_adopt_explanation_draft(expert_client) -> None:
    client, factory = expert_client
    db = factory()
    user = db.query(User).first()
    chat_session = ChatSession(user_id=user.id, snapshot_id=1, sku="SKU-001", warehouse="WH-A")
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)

    assistant = ChatMessage(
        session_id=chat_session.id,
        role="assistant",
        content="草稿",
        message_metadata={
            "explanation_draft": {
                "sku": "SKU-001",
                "warehouse": "WH-A",
                "primary_explanation": "测试主解释",
                "suggested_action": "补货",
            }
        },
    )
    db.add(assistant)
    db.commit()
    db.refresh(assistant)

    monitor = MagicMock(spec=FactMonitorResult)
    monitor.warehouse = "WH-A"
    monitor.risk_type = RiskType.STOCKOUT
    monitor.risk_level = RiskLevel.RED

    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    query_mock.first.return_value = monitor

    with patch("buque.services.expert_service.get_snapshot") as get_snapshot:
        get_snapshot.return_value = MagicMock(monitor_date=date(2026, 6, 23))
        with patch("buque.services.expert_service.event_id_for", return_value="evt-1"):
            existing = FactAgentExplain(
                snapshot_id=1,
                date=date(2026, 6, 23),
                sku="SKU-001",
                event_id="evt-1",
                primary_explanation="旧",
                suggested_action="旧",
                responsible_role="计划",
            )
            with patch.object(
                db,
                "query",
                side_effect=lambda model: (
                    query_mock
                    if model is FactMonitorResult
                    else MagicMock(
                        filter=MagicMock(
                            return_value=MagicMock(first=MagicMock(return_value=existing))
                        )
                    )
                ),
            ):
                with patch.object(db, "refresh"):
                    row = adopt_explanation_draft(db, chat_session, assistant.id)
                    assert row.primary_explanation == "测试主解释"
    db.close()


def test_fetch_alerts_no_filters_returns_items() -> None:
    from buque.services.expert_queries import fetch_alerts

    db = MagicMock()
    query_mock = MagicMock()
    query_mock.outerjoin.return_value = query_mock
    query_mock.filter.return_value = query_mock
    query_mock.count.return_value = 0
    query_mock.order_by.return_value = query_mock
    query_mock.offset.return_value = query_mock
    query_mock.limit.return_value = query_mock
    query_mock.all.return_value = []
    db.query.return_value = query_mock

    result = fetch_alerts(db, 1)
    assert "error" not in result
    assert result["items"] == []
    assert result["sort_hint"] == "risk_level desc, dos asc"


def test_stream_agent_turn_persists_process_trace(expert_client) -> None:
    from claude_agent_sdk import ResultMessage

    from buque.services.expert_agent import stream_agent_turn

    _, factory = expert_client
    db = factory()
    user = db.query(User).first()
    chat_session = ChatSession(user_id=user.id, snapshot_id=1)
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)

    async def fake_receive():
        yield ResultMessage(
            subtype="result",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="agent-session-1",
        )

    fake_client = MagicMock()
    fake_client.query = AsyncMock()
    fake_client.receive_response = fake_receive

    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_client)
    fake_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("buque.services.expert_agent.get_settings") as get_settings:
        get_settings.return_value = MagicMock(agent_enabled=True)
        with patch("buque.services.expert_agent.build_expert_tool_context") as build_ctx:
            build_ctx.return_value = MagicMock(explanation_draft=None)
            with patch("buque.services.expert_agent.build_agent_options", return_value=MagicMock()):
                with patch("buque.services.expert_agent.ClaudeSDKClient", return_value=fake_cm):

                    async def run():
                        events = []
                        async for event in stream_agent_turn(db, chat_session, "你好"):
                            events.append(event)
                        return events

                    events = asyncio.run(run())

    db.refresh(chat_session)
    assert chat_session.updated_at is not None
    assert any(event.event == "done" for event in events)
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == chat_session.id).all()
    assert len(messages) == 1
    assert messages[0].role == "assistant"
    meta = messages[0].message_metadata or {}
    assert isinstance(meta.get("process_duration_ms"), int)
    assert meta["process_duration_ms"] >= 0
    trace = meta.get("process_trace")
    if trace is not None:
        assert isinstance(trace, list)


def test_extract_sku_from_message() -> None:
    from buque.services.expert_agent import extract_sku_from_message

    assert extract_sku_from_message("看看 C0180444 怎么回事") == "C0180444"
    assert extract_sku_from_message("分析 SKU-001") == "SKU-001"


def test_stream_agent_turn_injects_sku_from_message(expert_client) -> None:
    from claude_agent_sdk import ResultMessage

    from buque.services.expert_agent import stream_agent_turn

    _, factory = expert_client
    db = factory()
    user = db.query(User).first()
    chat_session = ChatSession(user_id=user.id, snapshot_id=1)
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)

    captured_ctx = {}

    async def fake_receive():
        yield ResultMessage(
            subtype="result",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="agent-session-1",
        )

    fake_client = MagicMock()
    fake_client.query = AsyncMock()
    fake_client.receive_response = fake_receive

    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_client)
    fake_cm.__aexit__ = AsyncMock(return_value=None)

    def capture_ctx(*args, **kwargs):
        ctx = build_expert_tool_context(*args, **kwargs)
        captured_ctx["value"] = ctx
        return ctx

    from buque.services.expert_tools import build_expert_tool_context

    with patch("buque.services.expert_agent.get_settings") as get_settings:
        get_settings.return_value = MagicMock(agent_enabled=True)
        with patch("buque.services.expert_agent.build_expert_tool_context", side_effect=capture_ctx):
            with patch("buque.services.expert_agent.build_agent_options", return_value=MagicMock()):
                with patch("buque.services.expert_agent.ClaudeSDKClient", return_value=fake_cm):

                    async def run():
                        async for _ in stream_agent_turn(db, chat_session, "看看 C0180444 怎么回事"):
                            pass

                    asyncio.run(run())

    assert captured_ctx["value"].sku == "C0180444"


def test_stream_agent_turn_emits_tool_events(expert_client) -> None:
    from claude_agent_sdk import AssistantMessage, ResultMessage, ToolResultBlock, ToolUseBlock, UserMessage

    from buque.services.expert_agent import stream_agent_turn, tool_label

    _, factory = expert_client
    db = factory()
    user = db.query(User).first()
    chat_session = ChatSession(user_id=user.id, snapshot_id=1)
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)

    assert tool_label("mcp__buque__list_alerts") == "查询风险清单"

    tool_use = ToolUseBlock(id="t1", name="mcp__buque__list_alerts", input={"level": "red"})
    tool_result = ToolResultBlock(tool_use_id="t1", content="[]", is_error=False)

    async def fake_receive():
        yield AssistantMessage(model="test", content=[tool_use])
        yield UserMessage(content=[tool_result])
        yield ResultMessage(
            subtype="result",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="agent-session-1",
        )

    fake_client = MagicMock()
    fake_client.query = AsyncMock()
    fake_client.receive_response = fake_receive

    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_client)
    fake_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("buque.services.expert_agent.get_settings") as get_settings:
        get_settings.return_value = MagicMock(agent_enabled=True)
        with patch("buque.services.expert_agent.build_expert_tool_context") as build_ctx:
            build_ctx.return_value = MagicMock(explanation_draft=None)
            with patch("buque.services.expert_agent.build_agent_options", return_value=MagicMock()):
                with patch("buque.services.expert_agent.ClaudeSDKClient", return_value=fake_cm):

                    async def run():
                        events = []
                        async for event in stream_agent_turn(db, chat_session, "列出红色预警"):
                            events.append(event)
                        return events

                    events = asyncio.run(run())

    tool_events = [event for event in events if event.event == "tool"]
    tool_result_events = [event for event in events if event.event == "tool_result"]
    assert tool_events
    assert tool_events[0].data["tools"][0]["label"] == "查询风险清单"
    assert tool_events[0].data["tools"][0]["detail"] == "level=red"
    assert tool_result_events
    assert tool_result_events[0].data["tool_use_id"] == "t1"
    assert any(event.event == "status" and event.data.get("phase") == "thinking" for event in events)
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == chat_session.id).all()
    trace = (messages[0].message_metadata or {}).get("process_trace")
    assert any(step.get("kind") == "tool" and step.get("id") == "t1" for step in trace)
    tool_step = next(step for step in trace if step.get("id") == "t1")
    assert tool_step.get("detail") == "level=red"
    assert isinstance((messages[0].message_metadata or {}).get("process_duration_ms"), int)


def test_build_expert_tool_context() -> None:
    from buque.services.expert_tools import build_expert_tool_context

    db = MagicMock()
    with patch("buque.services.expert_tools.get_snapshot") as get_snapshot:
        get_snapshot.return_value = MagicMock(monitor_date=date(2026, 6, 23))
        ctx = build_expert_tool_context(
            db,
            snapshot_id=1,
            sku="SKU-001",
            warehouse="WH-A",
        )
    assert ctx.snapshot_id == 1
    assert ctx.monitor_date == date(2026, 6, 23)
    assert ctx.sku == "SKU-001"
    assert ctx.warehouse == "WH-A"


def test_propose_explanation_draft_tool() -> None:
    from buque.services.expert_tools import ExpertToolContext, create_buque_mcp_server

    ctx = ExpertToolContext(
        db=MagicMock(),
        snapshot_id=1,
        monitor_date=date(2026, 6, 23),
        sku="SKU-001",
    )
    server = create_buque_mcp_server(ctx)
    assert server is not None


def test_normalize_risk_level_aliases() -> None:
    from buque.models.entities import RiskLevel
    from buque.services.expert_queries import normalize_risk_level, normalize_risk_type

    assert normalize_risk_level("red") == RiskLevel.RED
    assert normalize_risk_level("红色") == RiskLevel.RED
    assert normalize_risk_level("invalid") is None
    assert normalize_risk_type("断货") == RiskType.STOCKOUT
    assert normalize_risk_type("unknown") is None


def test_fetch_alerts_invalid_level_returns_allowed(expert_client) -> None:
    from buque.services.expert_queries import fetch_alerts

    _, factory = expert_client
    db = factory()
    result = fetch_alerts(db, 1, level="not-a-level")
    assert result["error"]
    assert "RED" in result["allowed_levels"]
    assert result["items"] == []
    db.close()
