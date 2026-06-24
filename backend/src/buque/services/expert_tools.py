from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool
from sqlalchemy.orm import Session

from buque.services.expert_queries import (
    build_sku_context,
    dumps_json,
    fetch_alerts,
    fetch_daily_summary,
)
from buque.services.snapshot_query import get_snapshot

REQUIRED_DRAFT_FIELDS = (
    "primary_explanation",
    "suggested_action",
)

LIST_ALERTS_SCHEMA = {
    "level": {"type": "string", "description": "可选 RED/ORANGE/YELLOW/GREEN"},
    "risk_type": {"type": "string", "description": "可选 STOCKOUT/SLOW_MOVING 等"},
    "sku": {"type": "string", "description": "可选 SKU 模糊筛选"},
    "warehouse": {"type": "string", "description": "可选仓库筛选"},
    "page": {"type": "integer", "description": "页码，默认 1"},
    "page_size": {"type": "integer", "description": "每页条数，top N 时设为 N"},
}

GET_SKU_CONTEXT_SCHEMA = {
    "sku": {"type": "string", "description": "必填，从用户消息提取，如 C0180444"},
    "warehouse": {"type": "string", "description": "可选仓库"},
}


@dataclass
class ExpertToolContext:
    db: Session
    snapshot_id: int
    monitor_date: date
    sku: str | None = None
    warehouse: str | None = None
    explanation_draft: dict[str, Any] | None = field(default=None)


def _text_result(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": dumps_json(payload)}]}


def _error_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": dumps_json(payload)}],
        "is_error": True,
    }


def create_buque_mcp_server(ctx: ExpertToolContext):
    @tool(
        "get_daily_summary",
        "获取当前快照日报摘要、计数与 filter_schema（合法 level/risk_type 枚举）",
        {},
    )
    async def get_daily_summary_tool(args: dict[str, Any]) -> dict[str, Any]:
        _ = args
        return _text_result(fetch_daily_summary(ctx.db, ctx.snapshot_id))

    @tool(
        "list_alerts",
        "分页列出风险预警。所有筛选参数均为可选；不传则返回全快照清单。"
        "page_size 控制条数，结果已按 risk_level desc + dos asc 排序（top N 用 page_size=N）",
        LIST_ALERTS_SCHEMA,
    )
    async def list_alerts_tool(args: dict[str, Any]) -> dict[str, Any]:
        result = fetch_alerts(
            ctx.db,
            ctx.snapshot_id,
            level=args.get("level") or None,
            risk_type=args.get("risk_type") or None,
            warehouse=args.get("warehouse") or None,
            sku=args.get("sku") or None,
            page=int(args.get("page") or 1),
            page_size=int(args.get("page_size") or 20),
        )
        if result.get("error"):
            return _error_result(result)
        return _text_result(result)

    @tool(
        "get_sku_context",
        "获取指定 SKU 的库存销量监控上下文。sku 必填，从用户消息提取（如 C0180444）；warehouse 可选",
        GET_SKU_CONTEXT_SCHEMA,
    )
    async def get_sku_context_tool(args: dict[str, Any]) -> dict[str, Any]:
        sku = args.get("sku") or ctx.sku
        if not sku:
            return _error_result({"error": "缺少 sku 参数"})
        warehouse = args.get("warehouse") or ctx.warehouse
        return _text_result(
            build_sku_context(ctx.db, ctx.monitor_date, ctx.snapshot_id, sku, warehouse)
        )

    @tool(
        "propose_explanation_draft",
        "提交结构化解释草稿；仅 primary_explanation 与 suggested_action 必填",
        {
            "primary_explanation": {"type": "string"},
            "suggested_action": {"type": "string"},
            "sku": {"type": "string"},
            "warehouse": {"type": "string"},
            "secondary_explanation": {"type": "string"},
            "tertiary_explanation": {"type": "string"},
            "explanation_tags": {"type": "array"},
            "key_evidence": {"type": "array"},
            "responsible_role": {"type": "string"},
            "action_deadline": {"type": "string"},
            "require_human_confirm": {"type": "boolean"},
            "confidence_note": {"type": "string"},
        },
    )
    async def propose_explanation_draft_tool(args: dict[str, Any]) -> dict[str, Any]:
        missing = [f for f in REQUIRED_DRAFT_FIELDS if not args.get(f)]
        if missing:
            return _error_result({"error": f"解释草稿缺少必填字段: {', '.join(missing)}"})
        draft = {
            "sku": args.get("sku") or ctx.sku,
            "warehouse": args.get("warehouse") or ctx.warehouse,
            "primary_explanation": args["primary_explanation"],
            "secondary_explanation": args.get("secondary_explanation"),
            "tertiary_explanation": args.get("tertiary_explanation"),
            "explanation_tags": args.get("explanation_tags") or [],
            "key_evidence": args.get("key_evidence") or [],
            "suggested_action": args["suggested_action"],
            "responsible_role": args.get("responsible_role") or "计划主管",
            "action_deadline": args.get("action_deadline") or "当天确认",
            "require_human_confirm": bool(args.get("require_human_confirm", True)),
            "confidence_note": args.get("confidence_note"),
        }
        ctx.explanation_draft = draft
        return _text_result({"status": "draft_recorded", "draft": draft})

    return create_sdk_mcp_server(
        "buque",
        tools=[
            get_daily_summary_tool,
            list_alerts_tool,
            get_sku_context_tool,
            propose_explanation_draft_tool,
        ],
    )


def build_expert_tool_context(
    db: Session,
    *,
    snapshot_id: int,
    sku: str | None = None,
    warehouse: str | None = None,
) -> ExpertToolContext:
    job = get_snapshot(db, snapshot_id)
    return ExpertToolContext(
        db=db,
        snapshot_id=snapshot_id,
        monitor_date=job.monitor_date,
        sku=sku,
        warehouse=warehouse,
    )


def refresh_tool_context_dates(ctx: ExpertToolContext) -> None:
    job = get_snapshot(ctx.db, ctx.snapshot_id)
    ctx.monitor_date = job.monitor_date
