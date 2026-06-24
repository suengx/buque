from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)
from claude_agent_sdk.types import StreamEvent
from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.models.entities import ChatMessage, ChatSession
from buque.services.agent_runtime import build_agent_options
from buque.services.expert_tools import build_expert_tool_context


@dataclass
class StreamEventOut:
    event: str
    data: dict[str, Any]


def _extract_text(message: AssistantMessage) -> str:
    parts: list[str] = []
    for block in message.content:
        if isinstance(block, TextBlock):
            parts.append(block.text)
    return "".join(parts)


def _tool_summary(message: AssistantMessage) -> list[dict[str, str]]:
    summaries: list[dict[str, str]] = []
    for block in message.content:
        if isinstance(block, ToolUseBlock):
            summaries.append({"name": block.name, "id": block.id})
    return summaries


async def stream_agent_turn(
    db: Session,
    session: ChatSession,
    user_content: str,
) -> AsyncIterator[StreamEventOut]:
    settings = get_settings()
    if not settings.agent_enabled:
        yield StreamEventOut("error", {"message": "Agent 未配置（缺少 ANTHROPIC_AUTH_TOKEN / BASE_URL）"})
        return

    assistant_text = ""
    agent_session_id: str | None = None

    try:
        ctx = build_expert_tool_context(
            db,
            snapshot_id=session.snapshot_id,
            sku=session.sku,
            warehouse=session.warehouse,
        )
        options = build_agent_options(ctx, resume=session.agent_session_id)

        async with ClaudeSDKClient(options=options) as client:
            await client.query(user_content)
            async for message in client.receive_response():
                if hasattr(message, "subtype") and getattr(message, "subtype", None) == "init":
                    agent_session_id = getattr(message, "session_id", None)
                    if agent_session_id:
                        session.agent_session_id = agent_session_id
                        db.commit()
                    yield StreamEventOut(
                        "session",
                        {"agent_session_id": agent_session_id},
                    )
                    continue

                if isinstance(message, StreamEvent):
                    event = message.event or {}
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        chunk = str(delta["text"])
                        assistant_text += chunk
                        yield StreamEventOut("delta", {"text": chunk})
                    continue

                if isinstance(message, AssistantMessage):
                    text = _extract_text(message)
                    if text and text != assistant_text:
                        new_part = text[len(assistant_text) :]
                        assistant_text = text
                        if new_part:
                            yield StreamEventOut("delta", {"text": new_part})
                    tools = _tool_summary(message)
                    if tools:
                        yield StreamEventOut("tool", {"tools": tools})
                    continue

                if isinstance(message, ResultMessage):
                    if message.session_id and not session.agent_session_id:
                        session.agent_session_id = message.session_id
                        db.commit()
                    break
    except Exception as exc:
        yield StreamEventOut("error", {"message": str(exc)})
        return

    metadata: dict[str, Any] = {}
    if ctx.explanation_draft:
        metadata["explanation_draft"] = ctx.explanation_draft
        yield StreamEventOut("draft", {"draft": ctx.explanation_draft})

    if not assistant_text:
        assistant_text = "（助手未返回文本，请检查 Agent 配置。）"

    assistant_row = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=assistant_text,
        message_metadata=metadata,
    )
    db.add(assistant_row)
    session.updated_at = datetime.now(timezone.utc)
    if not session.title:
        session.title = user_content[:80]
    db.commit()
    db.refresh(assistant_row)

    yield StreamEventOut("done", {"message_id": assistant_row.id})


def format_sse(event: StreamEventOut) -> str:
    return f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
