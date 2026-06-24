from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from buque.api.deps import CurrentUser, auth_router_dependencies
from buque.db import get_db
from buque.schemas.expert import (
    AdoptExplanationOut,
    AdoptExplanationRequest,
    ChatMessageOut,
    ChatSessionDetailOut,
    ChatSessionOut,
    CreateSessionRequest,
    ExplanationDraftOut,
    SendMessageRequest,
)
from buque.services import expert_service as svc
from buque.services.expert_agent import format_sse, stream_agent_turn

router = APIRouter(
    prefix="/api/v1/expert",
    tags=["expert"],
    dependencies=auth_router_dependencies(),
)


def _message_out(row) -> ChatMessageOut:
    meta = row.message_metadata or {}
    draft_raw = meta.get("explanation_draft")
    draft = ExplanationDraftOut(**draft_raw) if draft_raw else None
    process_trace = meta.get("process_trace")
    process_duration_ms = meta.get("process_duration_ms")
    return ChatMessageOut(
        id=row.id,
        role=row.role,
        content=row.content,
        explanation_draft=draft,
        process_trace=process_trace,
        process_duration_ms=process_duration_ms,
        created_at=row.created_at,
    )


def _session_out(row) -> ChatSessionOut:
    return ChatSessionOut.model_validate(row)


@router.post("/sessions", response_model=ChatSessionOut)
def create_session(
    payload: CreateSessionRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> ChatSessionOut:
    title = None
    if payload.sku:
        title = f"SKU {payload.sku}"
    session = svc.create_session(
        db,
        current_user,
        snapshot_id=payload.snapshot_id,
        sku=payload.sku,
        warehouse=payload.warehouse,
        title=title,
    )
    return _session_out(session)


@router.get("/sessions", response_model=list[ChatSessionOut])
def list_sessions(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[ChatSessionOut]:
    rows = svc.list_sessions(db, current_user)
    return [_session_out(r) for r in rows]


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailOut)
def get_session(
    session_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> ChatSessionDetailOut:
    session = svc.get_owned_session(db, session_id, current_user)
    messages = svc.list_messages(db, session.id)
    base = _session_out(session)
    return ChatSessionDetailOut(
        **base.model_dump(),
        messages=[_message_out(m) for m in messages],
    )


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    payload: SendMessageRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    session = svc.get_owned_session(db, session_id, current_user)
    svc.add_user_message(db, session, payload.content)

    async def event_stream():
        async for event in stream_agent_turn(db, session, payload.content):
            yield format_sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/adopt-explanation", response_model=AdoptExplanationOut)
def adopt_explanation(
    session_id: int,
    payload: AdoptExplanationRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> AdoptExplanationOut:
    session = svc.get_owned_session(db, session_id, current_user)
    row = svc.adopt_explanation_draft(db, session, payload.message_id)
    return AdoptExplanationOut(
        snapshot_id=row.snapshot_id,
        sku=row.sku,
        primary_explanation=row.primary_explanation,
        suggested_action=row.suggested_action,
    )
