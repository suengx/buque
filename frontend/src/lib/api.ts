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

export type FeedbackStats = {
  total: number
  adopted: number
  rejected: number
  partial: number
  adoption_rate: number
}

export const api = {
  dailyReport: (date?: string) =>
    request<DailyReportSummary>(`/reports/daily${date ? `?monitor_date=${date}` : ''}`),
  alerts: (params: Record<string, string | number>) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => q.set(k, String(v)))
    return request<PaginatedAlerts>(`/alerts?${q}`)
  },
  skuDetail: (sku: string, warehouse?: string) =>
    request<SkuDetail>(
      `/alerts/${sku}${warehouse ? `?warehouse=${encodeURIComponent(warehouse)}` : ''}`,
    ),
  createFeedback: (body: Record<string, unknown>) =>
    request('/feedback', { method: 'POST', body: JSON.stringify(body) }),
  feedbackStats: () => request<FeedbackStats>('/feedback/stats'),
}

export const queryKeys = {
  dailyReport: (date?: string) => ['dailyReport', date] as const,
  alerts: (params: Record<string, string | number>) => ['alerts', params] as const,
  skuDetail: (sku: string, warehouse?: string) => ['skuDetail', sku, warehouse] as const,
  feedbackStats: ['feedbackStats'] as const,
}
