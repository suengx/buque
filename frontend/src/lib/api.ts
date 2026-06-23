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

export type DailyReportSummary = {
  monitor_date: string
  monitored_sku_count: number
  new_red_count: number
  new_orange_count: number
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

export type ErpSyncStatusResponse = {
  monitor_date: string
  running: boolean
  job_id: number | null
  job_status: string
  phase: string | null
  phase_message: string | null
  error: string | null
  finished_at: string | null
  sync_summary: Record<string, unknown> | null
  logs: { level: string; message: string; created_at: string }[]
  sources: IngestionSourceStatus[]
}

export type ErpSyncLatestResponse = {
  monitor_date: string
  has_sync: boolean
  job_id: number | null
  finished_at: string | null
  sync_summary: Record<string, unknown> | null
}

export type OpsStatusResponse = {
  monitor_date: string
  timezone: string
  schedule_label: string
  next_scheduled_at: string
  pipeline_active: boolean
  sync_running: boolean
  analysis_running: boolean
  sync_phase_message: string | null
  analysis_phase_message: string | null
  erp_configured: boolean
  latest_sync: ErpSyncLatestResponse
}

export type AnalysisStatusResponse = {
  monitor_date: string
  running: boolean
  job_id: number | null
  job_status: string
  phase: string | null
  phase_message: string | null
  error: string | null
  finished_at: string | null
  progress_current: number | null
  progress_total: number | null
  analysis_summary: Record<string, number> | null
  logs: { level: string; message: string; created_at: string }[]
}

export type AnalysisAccepted = {
  monitor_date: string
  job_id: number
  message: string
}

export type ErpSyncAccepted = {
  monitor_date: string
  job_id: number
  message: string
}

export type ReportAnalytics = {
  monitor_date: string
  level_counts: Record<string, number>
  type_counts: Record<string, number>
  trend_7d: { date: string; red: number; orange: number; yellow: number; green: number }[]
  top_priority: MonitorResult[]
}

export type AlertsMeta = {
  monitor_date: string
  warehouses: string[]
  type_counts: Record<string, number>
}

export type PipelineRunResult = {
  monitor_date: string
  ingestion: Record<string, number>
  quality_issues: number
  monitor_results: number
  events: number
  explained: number
}

export const api = {
  dailyReport: (date?: string) =>
    request<DailyReportSummary>(`/reports/daily${date ? `?monitor_date=${date}` : ''}`),
  reportAnalytics: (date?: string) =>
    request<ReportAnalytics>(`/reports/analytics${date ? `?monitor_date=${date}` : ''}`),
  alertsMeta: (date?: string) =>
    request<AlertsMeta>(`/alerts/meta${date ? `?monitor_date=${date}` : ''}`),
  alerts: (params: Record<string, string | number>) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => q.set(k, String(v)))
    return request<PaginatedAlerts>(`/alerts?${q}`)
  },
  skuDetail: (sku: string, warehouse?: string) =>
    request<SkuDetail>(
      `/alerts/${sku}${warehouse ? `?warehouse=${encodeURIComponent(warehouse)}` : ''}`,
    ),
  agentExplainSku: (sku: string, opts?: { warehouse?: string; monitorDate?: string }) => {
    const q = new URLSearchParams()
    if (opts?.warehouse) q.set('warehouse', opts.warehouse)
    if (opts?.monitorDate) q.set('monitor_date', opts.monitorDate)
    const suffix = q.toString() ? `?${q}` : ''
    return request<AgentExplainResult>(`/alerts/${encodeURIComponent(sku)}/agent-explain${suffix}`, {
      method: 'POST',
    })
  },
  createFeedback: (body: Record<string, unknown>) =>
    request('/feedback', { method: 'POST', body: JSON.stringify(body) }),
  feedbackStats: () => request<FeedbackStats>('/feedback/stats'),
  startErpSync: (opts: { monitorDate?: string }) =>
    request<ErpSyncAccepted>('/admin/sync/erp', {
      method: 'POST',
      body: JSON.stringify({
        monitor_date: opts.monitorDate,
      }),
    }),
  getErpSyncStatus: (monitorDate?: string, jobId?: number) => {
    const q = new URLSearchParams()
    if (monitorDate) q.set('monitor_date', monitorDate)
    if (jobId !== undefined) q.set('job_id', String(jobId))
    const suffix = q.toString() ? `?${q}` : ''
    return request<ErpSyncStatusResponse>(`/admin/sync/status${suffix}`)
  },
  getErpSyncLatest: (monitorDate?: string) => {
    const q = monitorDate ? `?monitor_date=${monitorDate}` : ''
    return request<ErpSyncLatestResponse>(`/admin/sync/latest${q}`)
  },
  getOpsStatus: (monitorDate?: string) => {
    const q = monitorDate ? `?monitor_date=${monitorDate}` : ''
    return request<OpsStatusResponse>(`/admin/ops/status${q}`)
  },
  startAnalysis: (opts: { monitorDate?: string }) =>
    request<AnalysisAccepted>('/admin/analyze', {
      method: 'POST',
      body: JSON.stringify({ monitor_date: opts.monitorDate }),
    }),
  getAnalysisStatus: (monitorDate?: string, jobId?: number) => {
    const q = new URLSearchParams()
    if (monitorDate) q.set('monitor_date', monitorDate)
    if (jobId !== undefined) q.set('job_id', String(jobId))
    const suffix = q.toString() ? `?${q}` : ''
    return request<AnalysisStatusResponse>(`/admin/analyze/status${suffix}`)
  },
  runPipeline: (opts: { monitorDate?: string; ingestionSource?: 'fixtures' | 'erp' }) => {
    const q = new URLSearchParams()
    if (opts.monitorDate) q.set('monitor_date', opts.monitorDate)
    if (opts.ingestionSource) q.set('ingestion_source', opts.ingestionSource)
    return request<PipelineRunResult>(`/admin/pipeline/run?${q}`, { method: 'POST' })
  },
}

export const queryKeys = {
  dailyReport: (date?: string) => ['dailyReport', date] as const,
  reportAnalytics: (date?: string) => ['reportAnalytics', date] as const,
  alertsMeta: (date?: string) => ['alertsMeta', date] as const,
  alerts: (params: Record<string, string | number>) => ['alerts', params] as const,
  skuDetail: (sku: string, warehouse?: string) => ['skuDetail', sku, warehouse] as const,
  feedbackStats: ['feedbackStats'] as const,
  opsStatus: (date?: string) => ['opsStatus', date] as const,
}
