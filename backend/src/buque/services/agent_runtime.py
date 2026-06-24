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
                "复杂查询前先 invoke buque-monitor skill，再按其中预设问法 JSON 示例调用；"
                "勿要求用户补充 list_alerts 本可不传的 sku/warehouse 参数。"
                "用户消息含 SKU 编码时直接 get_sku_context，勿追问、勿向用户解释工具定义。"
                "匹配预设问法时先调用工具再回答，禁止无工具凭空虚构清单。"
                "禁止在回复中讨论 MCP schema 或工具实现细节。"
            ),
        },
    )
