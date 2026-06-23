const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`)
  }
  return res.json() as Promise<T>
}

function snapshotQuery(snapshotId?: number) {
  return snapshotId ? `?snapshot_id=${snapshotId}` : ''
}

export type SnapshotSummary = {
  id: number
  monitor_date: string
  finished_at: string | null
  sync_summary: Record<string, unknown> | null
  analysis_summary: Record<string, number> | null
}

export type TrendComparison = {
  new_red_count: number
  new_orange_count: number
  baseline_label: string | null
  baseline_snapshot_id: number | null
  available: boolean
}

export type DailyReportSummary = {
  snapshot_id: number
  monitor_date: string
  monitored_sku_count: number
  new_red_count: number
  new_orange_count: number
  comparison_vs_prev_day: TrendComparison
  comparison_vs_prev_snapshot: TrendComparison
  stockout_high_risk_count: number
  slow_moving_high_risk_count: number
  sales_anomaly_count: number
  data_anomaly_count: number
  priority_today_count: number
}

export type MonitorResult = {
  id: number
  date: string
  sku: string
  product_name: string | null
  warehouse: string | null
  risk_type: string
  risk_level: string
  trigger_rule: string
  trigger_metrics: Record<string, unknown>
  dos: string | null
  primary_explanation: string | null
  suggested_action: string | null
  responsible_role: string | null
  handling_status: string
}

export type PaginatedAlerts = {
  items: MonitorResult[]
  total: number
  page: number
  page_size: number
}

export type SkuDetail = {
  snapshot_id: number
  monitor_date: string
  sku: string
  product_name: string | null
  warehouse: string | null
  risk_type: string
  risk_level: string
  trigger_metrics: Record<string, unknown>
  dos: string | null
  primary_explanation: string | null
  secondary_explanation: string | null
  tertiary_explanation: string | null
  key_evidence: string[]
  suggested_action: string | null
  responsible_role: string | null
  action_deadline: string | null
  require_human_confirm: boolean
}

export type AgentExplainResult = {
  primary_explanation: string
  secondary_explanation: string | null
  tertiary_explanation: string | null
  explanation_tags: string[]
  key_evidence: string[]
  suggested_action: string
  responsible_role: string | null
  action_deadline: string | null
  require_human_confirm: boolean
  confidence_note: string | null
}

export type FeedbackStats = {
  total: number
  adopted: number
  rejected: number
  partial: number
  adoption_rate: number
}

export type IngestionSourceStatus = {
  source: string
  status: string
  row_count: number
  file_path: string | null
  error: string | null
  finished_at: string | null
  ingestion_run_id: number | null
}

export type PipelineStatusResponse = {
  snapshot_id: number | null
  monitor_date: string
  running: boolean
  job_status: string
  phase: string | null
  phase_message: string | null
  error: string | null
  finished_at: string | null
  sync_summary: Record<string, unknown> | null
  analysis_summary: Record<string, number> | null
  progress_current: number | null
  progress_total: number | null
  logs: { level: string; message: string; created_at: string }[]
  sources: IngestionSourceStatus[]
}

export type PipelineAccepted = {
  snapshot_id: number
  monitor_date: string
  message: string
}

export type OpsStatusResponse = {
  timezone: string
  schedule_label: string
  next_scheduled_at: string
  pipeline_active: boolean
  running_snapshot_id: number | null
  phase_message: string | null
  erp_configured: boolean
}

export type ReportAnalytics = {
  snapshot_id: number
  monitor_date: string
  level_counts: Record<string, number>
  type_counts: Record<string, number>
  trend_7d: { date: string; red: number; orange: number; yellow: number; green: number }[]
  top_priority: MonitorResult[]
}

export type AlertsMeta = {
  snapshot_id: number
  monitor_date: string
  warehouses: string[]
  type_counts: Record<string, number>
}

export type PipelineRunResult = {
  snapshot_id: number
  monitor_date: string
  ingestion: Record<string, number>
  quality_issues: number
  monitor_results: number
  events: number
  explained: number
}

export type RuleConfigItem = {
  rule_code: string
  rule_name: string
  param_value: string
  param_type: string
  version: number
  effective_date: string
  is_enabled: boolean
  change_reason?: string | null
  proposer?: string | null
  category: string
  description: string
  editor: string
}

export type RuleGroup = {
  category: string
  category_label: string
  rules: RuleConfigItem[]
}

export type MetricLabel = {
  rule_code: string
  label: string
  short_label: string
}

export type MetricLabels = {
  risk_levels: Record<string, MetricLabel[]>
  special_risks: Record<string, MetricLabel[]>
  section_descriptions: Record<string, string>
}

export const api = {
  dailyReport: (snapshotId?: number) =>
    request<DailyReportSummary>(`/reports/daily${snapshotQuery(snapshotId)}`),
  reportAnalytics: (snapshotId?: number) =>
    request<ReportAnalytics>(`/reports/analytics${snapshotQuery(snapshotId)}`),
  alertsMeta: (snapshotId?: number) =>
    request<AlertsMeta>(`/alerts/meta${snapshotQuery(snapshotId)}`),
  alerts: (params: Record<string, string | number>) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => q.set(k, String(v)))
    return request<PaginatedAlerts>(`/alerts?${q}`)
  },
  skuDetail: (sku: string, opts?: { warehouse?: string; snapshotId?: number }) => {
    const q = new URLSearchParams()
    if (opts?.warehouse) q.set('warehouse', opts.warehouse)
    if (opts?.snapshotId) q.set('snapshot_id', String(opts.snapshotId))
    const suffix = q.toString() ? `?${q}` : ''
    return request<SkuDetail>(`/alerts/${sku}${suffix}`)
  },
  agentExplainSku: (sku: string, opts?: { warehouse?: string; snapshotId?: number }) => {
    const q = new URLSearchParams()
    if (opts?.warehouse) q.set('warehouse', opts.warehouse)
    if (opts?.snapshotId) q.set('snapshot_id', String(opts.snapshotId))
    const suffix = q.toString() ? `?${q}` : ''
    return request<AgentExplainResult>(`/alerts/${encodeURIComponent(sku)}/agent-explain${suffix}`, {
      method: 'POST',
    })
  },
  createFeedback: (body: Record<string, unknown>) =>
    request('/feedback', { method: 'POST', body: JSON.stringify(body) }),
  feedbackStats: () => request<FeedbackStats>('/feedback/stats'),
  listSnapshots: () => request<SnapshotSummary[]>('/admin/snapshots'),
  startPipeline: (opts: { monitorDate?: string }) =>
    request<PipelineAccepted>('/admin/pipeline/start', {
      method: 'POST',
      body: JSON.stringify({ monitor_date: opts.monitorDate }),
    }),
  getPipelineStatus: (jobId?: number) => {
    const q = jobId !== undefined ? `?job_id=${jobId}` : ''
    return request<PipelineStatusResponse>(`/admin/pipeline/status${q}`)
  },
  getOpsStatus: () => request<OpsStatusResponse>('/admin/ops/status'),
  runPipeline: (opts: { monitorDate?: string; ingestionSource?: 'fixtures' | 'erp' }) => {
    const q = new URLSearchParams()
    if (opts.monitorDate) q.set('monitor_date', opts.monitorDate)
    if (opts.ingestionSource) q.set('ingestion_source', opts.ingestionSource)
    return request<PipelineRunResult>(`/admin/pipeline/run?${q}`, { method: 'POST' })
  },
  listRules: () => request<{ groups: RuleGroup[] }>('/rules'),
  getMetricLabels: () => request<MetricLabels>('/rules/metric-labels'),
  getRuleHistory: (ruleCode: string) =>
    request<RuleConfigItem[]>(`/rules/${encodeURIComponent(ruleCode)}/history`),
  updateRule: (
    ruleCode: string,
    body: {
      param_value?: string
      is_enabled?: boolean
      change_reason: string
      proposer?: string
    },
  ) =>
    request<RuleConfigItem>(`/rules/${encodeURIComponent(ruleCode)}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
}

export const queryKeys = {
  snapshots: ['snapshots'] as const,
  dailyReport: (snapshotId?: number) => ['dailyReport', snapshotId] as const,
  reportAnalytics: (snapshotId?: number) => ['reportAnalytics', snapshotId] as const,
  alertsMeta: (snapshotId?: number) => ['alertsMeta', snapshotId] as const,
  alerts: (params: Record<string, string | number>) => ['alerts', params] as const,
  skuDetail: (sku: string, snapshotId?: number, warehouse?: string) =>
    ['skuDetail', sku, snapshotId, warehouse] as const,
  feedbackStats: ['feedbackStats'] as const,
  opsStatus: ['opsStatus'] as const,
  rules: ['rules'] as const,
  metricLabels: ['metricLabels'] as const,
  ruleHistory: (code: string) => ['ruleHistory', code] as const,
}
