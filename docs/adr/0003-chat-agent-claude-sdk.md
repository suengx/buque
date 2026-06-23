# 用户侧 Agent 统一为监控助手 Chat（Claude Agent SDK）

补雀只保留一套用户侧 LLM 能力：**监控助手 Chat**（Claude Agent SDK + 领域 Skill + MCP tools）。日批流水线仅用规则引擎写 `fact_agent_explain`；任何 LLM 调用只出现在用户发起的 Chat 中。SKU 卡「深度分析」并入 Chat 首条自动消息；`propose_explanation_draft` tool 产出可采纳的解释草稿，人工「采纳解释」后才写入 `fact_agent_explain`，「提交反馈」仍走 `fact_feedback`，两步分离。会话绑定 `snapshot_id`（可选预填 sku/warehouse），`chat_session` + `chat_message` 全量落库并关联 `user_id`（登录注册与 Chat 并行开发，上线前 `user_id` 不可空）。

**Considered Options:** 保留 `ExplainerAgent` 单次 httpx 与 Chat 双轨（否决：多套 Agent 心智与维护成本）；日批静默 LLM 预生成草稿（否决：破坏日批确定性与 Excel 对齐）；自写 Messages API tool loop（否决：Chat 需要的会话、流式、turn/budget 治理 SDK 已预设）；自由文本抽取采纳（否决：`propose_explanation_draft` 与 `fact_agent_explain` 字段对齐更可审计）。

**Consequences:** 后端需引入 `claude-agent-sdk` 及 CLI 部署；废弃对用户暴露的 `POST /agent-explain`；MVP 只读 tools 为 `get_daily_summary`、`list_alerts`、`get_sku_context` 三件套；领域口径通过 `backend/.claude/skills/buque-monitor/SKILL.md` 注入，与 MCP tools 分工（Skill=怎么理解，Tool=查什么事实）。
