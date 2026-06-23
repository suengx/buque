import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { BarChart3, CircleAlert, OctagonAlert, TriangleAlert } from 'lucide-react'
import { api, queryKeys } from '#/lib/api'
import { RISK_LEVEL_LABEL, riskTypeLabel } from '#/lib/labels'
import { useSnapshot } from '#/context/SnapshotContext'
import { AlertDetailModal, type AlertDetailTarget } from '#/components/buque/AlertDetailModal'
import { AlertsTable } from '#/components/buque/AlertsTable'
import { CategoryDistribution } from '#/components/buque/CategoryDistribution'
import { FilterBar, type FilterValues } from '#/components/buque/FilterBar'
import { MetricCard } from '#/components/buque/MetricCard'
import { PageHeader } from '#/components/buque/PageHeader'
import { RiskTrendChart } from '#/components/buque/ReportCharts'
import {
  levelDistributionItems,
  typeDistributionItems,
} from '#/lib/risk-tokens'

type AlertsSearch = {
  level?: string
  risk_type?: string
  warehouse?: string
  sku?: string
  page?: number
}

export const Route = createFileRoute('/alerts/')({
  validateSearch: (search: Record<string, unknown>): AlertsSearch => ({
    level: (search.level as string) || undefined,
    risk_type: (search.risk_type as string) || undefined,
    warehouse: (search.warehouse as string) || undefined,
    sku: (search.sku as string) || undefined,
    page: search.page ? Number(search.page) : 1,
  }),
  component: AlertsPage,
})

const PAGE_SIZE = 20

function pct(count: number, total: number) {
  if (total <= 0) return '0%'
  return `${((count / total) * 100).toFixed(1)}%`
}

function AlertsPage() {
  const navigate = useNavigate({ from: '/alerts/' })
  const search = Route.useSearch()
  const { selectedSnapshotId } = useSnapshot()
  const [detailTarget, setDetailTarget] = useState<AlertDetailTarget | null>(null)
  const [draft, setDraft] = useState<FilterValues>({
    level: search.level,
    risk_type: search.risk_type,
    warehouse: search.warehouse,
    sku: search.sku,
  })

  const { data: meta } = useQuery({
    queryKey: queryKeys.alertsMeta(selectedSnapshotId),
    queryFn: () => api.alertsMeta(selectedSnapshotId),
    enabled: selectedSnapshotId !== undefined,
  })

  const { data: analytics } = useQuery({
    queryKey: queryKeys.reportAnalytics(selectedSnapshotId),
    queryFn: () => api.reportAnalytics(selectedSnapshotId),
    enabled: selectedSnapshotId !== undefined,
  })

  const { data: metricLabels } = useQuery({
    queryKey: queryKeys.metricLabels,
    queryFn: () => api.getMetricLabels(),
  })

  const alertParams: Record<string, string | number> = {
    page: search.page ?? 1,
    page_size: PAGE_SIZE,
  }
  if (selectedSnapshotId) alertParams.snapshot_id = selectedSnapshotId
  if (search.level) alertParams.level = search.level
  if (search.risk_type) alertParams.risk_type = search.risk_type
  if (search.warehouse) alertParams.warehouse = search.warehouse
  if (search.sku) alertParams.sku = search.sku

  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.alerts(alertParams),
    queryFn: () => api.alerts(alertParams),
    enabled: selectedSnapshotId !== undefined,
  })

  const levels = analytics?.level_counts ?? {}
  const low = levels.YELLOW ?? 0
  const mid = levels.ORANGE ?? 0
  const high = levels.RED ?? 0
  const totalAlerts = low + mid + high

  const applyFilters = () => {
    navigate({
      search: {
        level: draft.level,
        risk_type: draft.risk_type,
        warehouse: draft.warehouse,
        sku: draft.sku,
        page: 1,
      },
    })
  }

  const resetFilters = () => {
    setDraft({})
    navigate({ search: { page: 1 } })
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1
  const currentPage = search.page ?? 1

  const hasActiveFilters = Boolean(search.level || search.risk_type || search.warehouse || search.sku)

  const filterLevel = (level: string) => navigate({ search: { ...search, level, page: 1 } })
  const filterType = (risk_type: string) => navigate({ search: { ...search, risk_type, page: 1 } })

  return (
    <div className="buque-page-stack">
      <PageHeader
        title="风险预警中心"
        tooltip="清单默认仓库作用域；主解释来自规则引擎批量写入。"
      />

      <FilterBar
        values={draft}
        warehouses={meta?.warehouses ?? []}
        onChange={(patch) => setDraft((prev) => ({ ...prev, ...patch }))}
        onReset={resetFilters}
        onSubmit={applyFilters}
      />

      {hasActiveFilters ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-[var(--sea-ink-soft)]">已筛选</span>
          {search.level ? <span className="buque-filter-chip">等级 · {RISK_LEVEL_LABEL[search.level] ?? search.level}</span> : null}
          {search.risk_type ? <span className="buque-filter-chip">类型 · {riskTypeLabel(search.risk_type)}</span> : null}
          {search.warehouse ? <span className="buque-filter-chip">仓库 · {search.warehouse}</span> : null}
          {search.sku ? <span className="buque-filter-chip">SKU · {search.sku}</span> : null}
        </div>
      ) : null}

      <div className="buque-metric-grid buque-metric-grid-4">
        <MetricCard
          badge="低风险"
          value={low}
          percent={pct(low, totalAlerts)}
          metricLabels={metricLabels?.risk_levels.YELLOW}
          icon={CircleAlert}
          accent="yellow"
          onClick={() => navigate({ search: { level: 'YELLOW', page: 1 } })}
        />
        <MetricCard
          badge="中风险"
          value={mid}
          percent={pct(mid, totalAlerts)}
          metricLabels={metricLabels?.risk_levels.ORANGE}
          icon={TriangleAlert}
          accent="orange"
          onClick={() => navigate({ search: { level: 'ORANGE', page: 1 } })}
        />
        <MetricCard
          badge="高风险"
          value={high}
          percent={pct(high, totalAlerts)}
          metricLabels={metricLabels?.risk_levels.RED}
          icon={OctagonAlert}
          accent="red"
          onClick={() => navigate({ search: { level: 'RED', page: 1 } })}
        />
        <MetricCard
          title="总预警数"
          value={totalAlerts}
          description="红 + 橙 + 黄预警行合计"
          icon={BarChart3}
          accent="neutral"
          onClick={() => navigate({ search: { page: 1 } })}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
        <AlertsTable
          data={data}
          isLoading={isLoading}
          error={error}
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={(page) => navigate({ search: { ...search, page } })}
          onViewDetail={setDetailTarget}
        />
        <div className="flex flex-col gap-3">
          {analytics ? (
            <CategoryDistribution
              title="风险等级分布"
              subtitle="红 / 橙 / 黄"
              items={levelDistributionItems(analytics.level_counts, false)}
              onBarClick={filterLevel}
              bordered
            />
          ) : null}
          {analytics ? <RiskTrendChart trend={analytics.trend_7d} compact /> : null}
          {analytics ? (
            <CategoryDistribution
              title="风险类型分布"
              subtitle="全等级计数"
              items={typeDistributionItems(analytics.type_counts)}
              onBarClick={filterType}
              bordered
            />
          ) : null}
        </div>
      </div>

      <AlertDetailModal target={detailTarget} onClose={() => setDetailTarget(null)} />
    </div>
  )
}
