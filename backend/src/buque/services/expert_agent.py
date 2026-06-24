from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from claude_agent_sdk.types import StreamEvent, TaskProgressMessage, TaskStartedMessage
from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.models.entities import ChatMessage, ChatSession
from buque.services.agent_runtime import build_agent_options
from buque.services.expert_tools import build_expert_tool_context

TOOL_LABELS: dict[str, str] = {
    "get_daily_summary": "查询日报摘要",
    "list_alerts": "查询风险清单",
    "get_sku_context": "获取 SKU 上下文",
    "propose_explanation_draft": "生成解释草稿",
}

HIDDEN_TRACE_PHASES = frozenset({"started", "saving"})

SKU_PATTERNS = (
    re.compile(r"\bSKU[-_]?\w+\b", re.IGNORECASE),
    re.compile(r"\b[A-Z]\d{5,}\b"),
    re.compile(r"\b[A-Z0-9]{5,}\b"),
)


@dataclass
class StreamEventOut:
    event: str
    data: dict[str, Any]


def extract_sku_from_message(text: str) -> str | None:
    for pattern in SKU_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_tool_name(name: str) -> str:
    prefix = "mcp__buque__"
    if name.startswith(prefix):
        return name[len(prefix) :]
    return name


def tool_label(name: str) -> str:
    short = _normalize_tool_name(name)
    return TOOL_LABELS.get(short, short)


def _format_tool_detail(tool_input: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in tool_input.items():
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    return ", ".join(parts)


def _tool_payload(block: ToolUseBlock) -> dict[str, Any]:
    short = _normalize_tool_name(block.name)
    tool_input = block.input if isinstance(block.input, dict) else {}
    detail = _format_tool_detail(tool_input)
    return {
        "id": block.id,
        "name": short,
        "label": tool_label(block.name),
        "detail": detail,
    }


def _tool_result_payload(block: ToolResultBlock, name_by_id: dict[str, str]) -> dict[str, Any]:
    short = name_by_id.get(block.tool_use_id, block.tool_use_id)
    return {
        "tool_use_id": block.tool_use_id,
        "name": short,
        "label": TOOL_LABELS.get(short, short),
        "is_error": bool(block.is_error),
    }


def _append_status(process_trace: list[dict[str, Any]], phase: str, label: str) -> None:
    if phase in HIDDEN_TRACE_PHASES:
        return
    if (
        process_trace
        and process_trace[-1].get("kind") == "status"
        and process_trace[-1].get("phase") == phase
    ):
        process_trace[-1]["label"] = label
        process_trace[-1]["at"] = _now_iso()
        return
    process_trace.append(
        {"kind": "status", "phase": phase, "label": label, "at": _now_iso()},
    )


def _append_tool(process_trace: list[dict[str, Any]], tool: dict[str, Any]) -> None:
    process_trace.append(
        {
            "kind": "tool",
            "id": tool["id"],
            "name": tool["name"],
            "label": tool["label"],
            "detail": tool.get("detail") or "",
            "status": "running",
            "at": _now_iso(),
        },
    )


def _mark_tool_result(
    process_trace: list[dict[str, Any]],
    tool_use_id: str,
    *,
    is_error: bool,
) -> None:
    for step in reversed(process_trace):
        if step.get("kind") == "tool" and step.get("id") == tool_use_id:
            step["status"] = "error" if is_error else "done"
            return


def compress_process_trace(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compressed: list[dict[str, Any]] = []
    for step in steps:
        if step.get("kind") == "status" and step.get("phase") in HIDDEN_TRACE_PHASES:
            continue
        if (
            compressed
            and step.get("kind") == "status"
            and compressed[-1].get("kind") == "status"
            and compressed[-1].get("phase") == step.get("phase")
        ):
            compressed[-1] = dict(step)
            continue
        compressed.append(dict(step))
    return compressed


def _extract_text(message: AssistantMessage) -> str:
    parts: list[str] = []
    for block in message.content:
        if isinstance(block, TextBlock):
            parts.append(block.text)
    return "".join(parts)


def _has_thinking(message: AssistantMessage) -> bool:
    return any(isinstance(block, ThinkingBlock) for block in message.content)


def _tool_uses(message: AssistantMessage) -> list[dict[str, Any]]:
    return [_tool_payload(block) for block in message.content if isinstance(block, ToolUseBlock)]


def _tool_results_from_content(
    content: list[Any],
    name_by_id: dict[str, str],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for block in content:
        if isinstance(block, ToolResultBlock):
            results.append(_tool_result_payload(block, name_by_id))
    return results


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
    tool_names_by_id: dict[str, str] = {}
    process_trace: list[dict[str, Any]] = []
    turn_started_at = datetime.now(timezone.utc)

    try:
        ctx = build_expert_tool_context(
            db,
            snapshot_id=session.snapshot_id,
            sku=session.sku,
            warehouse=session.warehouse,
        )
        if not ctx.sku:
            extracted = extract_sku_from_message(user_content)
            if extracted:
                ctx.sku = extracted

        options = build_agent_options(ctx, resume=session.agent_session_id)

        _append_status(process_trace, "started", "正在连接助手…")
        yield StreamEventOut(
            "status",
            {"phase": "started", "label": "正在连接助手…"},
        )

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

                if isinstance(message, TaskStartedMessage):
                    label = message.description or "正在调用工具…"
                    _append_status(process_trace, "tool_running", label)
                    yield StreamEventOut(
                        "status",
                        {"phase": "tool_running", "label": label},
                    )
                    continue

                if isinstance(message, TaskProgressMessage):
                    last_tool = message.last_tool_name
                    label = message.description or (
                        tool_label(last_tool) if last_tool else "正在处理…"
                    )
                    yield StreamEventOut(
                        "progress",
                        {
                            "description": message.description,
                            "last_tool_name": _normalize_tool_name(last_tool) if last_tool else None,
                            "label": label,
                        },
                    )
                    if last_tool:
                        _append_status(process_trace, "tool_running", label)
                        yield StreamEventOut(
                            "status",
                            {"phase": "tool_running", "label": label},
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
                    if _has_thinking(message):
                        _append_status(process_trace, "thinking", "正在思考…")
                        yield StreamEventOut(
                            "status",
                            {"phase": "thinking", "label": "正在思考…"},
                        )
                    text = _extract_text(message)
                    if text and text != assistant_text:
                        new_part = text[len(assistant_text) :]
                        assistant_text = text
                        if new_part:
                            yield StreamEventOut("delta", {"text": new_part})
                    tools = _tool_uses(message)
                    if tools:
                        for tool in tools:
                            tool_names_by_id[tool["id"]] = tool["name"]
                            _append_tool(process_trace, tool)
                        yield StreamEventOut(
                            "tool",
                            {"tools": tools, "status": "started"},
                        )
                        tool_label_text = "、".join(t["label"] for t in tools)
                        _append_status(process_trace, "tool_running", tool_label_text)
                        yield StreamEventOut(
                            "status",
                            {
                                "phase": "tool_running",
                                "label": tool_label_text,
                            },
                        )
                    continue

                if isinstance(message, UserMessage):
                    results = _tool_results_from_content(message.content, tool_names_by_id)
                    for result in results:
                        _mark_tool_result(
                            process_trace,
                            result["tool_use_id"],
                            is_error=bool(result["is_error"]),
                        )
                        yield StreamEventOut("tool_result", result)
                    if results:
                        _append_status(process_trace, "thinking", "正在思考…")
                        yield StreamEventOut(
                            "status",
                            {"phase": "thinking", "label": "正在思考…"},
                        )
                    continue

                if isinstance(message, ResultMessage):
                    if message.session_id and not session.agent_session_id:
                        session.agent_session_id = message.session_id
                        db.commit()
                    break
    except Exception as exc:
        yield StreamEventOut("error", {"message": str(exc)})
        return

    process_duration_ms = int(
        (datetime.now(timezone.utc) - turn_started_at).total_seconds() * 1000,
    )
    compressed_trace = compress_process_trace(process_trace)

    metadata: dict[str, Any] = {"process_duration_ms": process_duration_ms}
    if compressed_trace:
        metadata["process_trace"] = compressed_trace
    if ctx.explanation_draft:
        metadata["explanation_draft"] = ctx.explanation_draft
        yield StreamEventOut("draft", {"draft": ctx.explanation_draft})

    if not assistant_text:
        assistant_text = "（助手未返回文本，请检查 Agent 配置。）"

    _append_status(process_trace, "saving", "正在保存…")
    yield StreamEventOut("status", {"phase": "saving", "label": "正在保存…"})

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
