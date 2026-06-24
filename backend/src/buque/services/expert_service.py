from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from buque.models.entities import (
    ChatMessage,
    ChatSession,
    FactAgentExplain,
    FactMonitorResult,
    MonitoringScope,
    User,
)
from buque.services.explanation_engine import event_id_for
from buque.services.snapshot_query import get_snapshot


def get_owned_session(db: Session, session_id: int, user: User) -> ChatSession:
    row = db.get(ChatSession, session_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return row


def create_session(
    db: Session,
    user: User,
    *,
    snapshot_id: int,
    sku: str | None = None,
    warehouse: str | None = None,
    title: str | None = None,
) -> ChatSession:
    get_snapshot(db, snapshot_id)
    row = ChatSession(
        user_id=user.id,
        snapshot_id=snapshot_id,
        sku=sku,
        warehouse=warehouse,
        title=title,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_sessions(db: Session, user: User, *, limit: int = 50) -> list[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
        .all()
    )


def list_messages(db: Session, session_id: int) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.asc())
        .all()
    )


def add_user_message(db: Session, session: ChatSession, content: str) -> ChatMessage:
    row = ChatMessage(session_id=session.id, role="user", content=content, message_metadata={})
    db.add(row)
    session.updated_at = datetime.now(timezone.utc)
    if not session.title:
        session.title = content[:80]
    db.commit()
    db.refresh(row)
    return row


def adopt_explanation_draft(
    db: Session,
    session: ChatSession,
    message_id: int,
) -> FactAgentExplain:
    message = db.get(ChatMessage, message_id)
    if message is None or message.session_id != session.id or message.role != "assistant":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在")
    draft = (message.message_metadata or {}).get("explanation_draft")
    if not draft:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该消息无解释草稿")

    sku = draft.get("sku") or session.sku
    if not sku:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="草稿缺少 SKU")

    warehouse = draft.get("warehouse") or session.warehouse
    job = get_snapshot(db, session.snapshot_id)
    monitor_q = db.query(FactMonitorResult).filter(
        FactMonitorResult.snapshot_id == session.snapshot_id,
        FactMonitorResult.sku == sku,
        FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
    )
    if warehouse:
        monitor_q = monitor_q.filter(FactMonitorResult.warehouse == warehouse)
    result = monitor_q.order_by(FactMonitorResult.risk_level.desc()).first()
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SKU 监控结果不存在")

    eid = event_id_for(session.snapshot_id, job.monitor_date, sku, result.warehouse, result.risk_type)
    existing = (
        db.query(FactAgentExplain)
        .filter(
            FactAgentExplain.snapshot_id == session.snapshot_id,
            FactAgentExplain.event_id == eid,
        )
        .first()
    )
    fields = {
        "primary_explanation": draft["primary_explanation"],
        "secondary_explanation": draft.get("secondary_explanation"),
        "tertiary_explanation": draft.get("tertiary_explanation"),
        "explanation_tags": draft.get("explanation_tags") or [],
        "key_evidence": draft.get("key_evidence") or [],
        "suggested_action": draft["suggested_action"],
        "responsible_role": draft.get("responsible_role") or "计划主管",
        "action_deadline": draft.get("action_deadline") or "当天确认",
        "require_human_confirm": bool(draft.get("require_human_confirm", True)),
        "confidence_note": draft.get("confidence_note"),
        "raw_response": draft,
    }
    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
        row = existing
    else:
        row = FactAgentExplain(
            snapshot_id=session.snapshot_id,
            date=job.monitor_date,
            sku=sku,
            event_id=eid,
            **fields,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row
