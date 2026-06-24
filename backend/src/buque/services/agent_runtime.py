from __future__ import annotations

from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions

from buque.config import get_settings
from buque.services.expert_tools import ExpertToolContext, create_buque_mcp_server

BACKEND_ROOT = Path(__file__).resolve().parents[3]

ALLOWED_TOOLS = [
    "mcp__buque__get_daily_summary",
    "mcp__buque__list_alerts",
    "mcp__buque__get_sku_context",
    "mcp__buque__propose_explanation_draft",
    "Skill",
]


def build_agent_options(
    ctx: ExpertToolContext,
    *,
    resume: str | None = None,
) -> ClaudeAgentOptions:
    settings = get_settings()
    buque_server = create_buque_mcp_server(ctx)
    return ClaudeAgentOptions(
        model=settings.agent_model,
        resume=resume,
        include_partial_messages=settings.stream_mode,
        setting_sources=["project"],
        skills=["buque-monitor"],
        tools=[],
        allowed_tools=ALLOWED_TOOLS,
        permission_mode="bypassPermissions",
        max_turns=settings.agent_max_turns,
        cwd=str(BACKEND_ROOT),
        mcp_servers={"buque": buque_server},
        env={
            "ANTHROPIC_AUTH_TOKEN": settings.anthropic_auth_token,
            "ANTHROPIC_BASE_URL": settings.anthropic_base_url,
            "ANTHROPIC_API_KEY": "",
        },
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": (
                "\n\n你是补雀监控助手。仅使用 buque MCP 工具查询事实；"
                "解释草稿须通过 propose_explanation_draft 提交。"
            ),
        },
    )
