import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import {
  BellRing,
  Boxes,
  CircleAlert,
  CircleCheck,
  Database,
  OctagonAlert,
  PackageX,
  TriangleAlert,
  TrendingDown,
} from 'lucide-react'
import { api, queryKeys } from '#/lib/api'
import { useSnapshot } from '#/context/SnapshotContext'
import { DailyTrendPanel } from '#/components/buque/DailyTrendPanel'
import { DistributionPanel } from '#/components/buque/DistributionPanel'
import { MetricCard } from '#/components/buque/MetricCard'
import { PageHeader } from '#/components/buque/PageHeader'
import { SectionBlock } from '#/components/buque/SectionBlock'

export const Route = createFileRoute('/_app/')({
  component: DailyReportPage,
})

function pct(count: number, total: number) {
  if (total <= 0) return '0%'
  return `${((count / total) * 100).toFixed(1)}%`
}

function snapshotSubtitle(snapshot: { monitor_date: string; finished_at: string | null } | undefined) {
  if (!snapshot) return undefined
  const time = snapshot.finished_at
    ? new Date(snapshot.finished_at).toLocaleString('zh-CN', {
        timeZone: 'Asia/Shanghai',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })
    : '—'
  return `当前快照 ${time} · 业务日 ${snapshot.monitor_date}`
}

function DailyReportPage() {
  const navigate = useNavigate()
  const { selectedSnapshotId, selectedSnapshot } = useSnapshot()

  const { data: daily, isLoading, error } = useQuery({
    queryKey: queryKeys.dailyReport(selectedSnapshotId),
    queryFn: () => api.dailyReport(selectedSnapshotId),
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

  const levels = analytics?.level_counts ?? {}
  const totalAlerts =
    (levels.RED ?? 0) + (levels.ORANGE ?? 0) + (levels.YELLOW ?? 0)

  const goAlerts = (search: Record<string, string>) => {
    navigate({ to: '/alerts', search })
  }

  if (!selectedSnapshotId) return <div className="demo-muted">加载快照…</div>
  if (isLoading) return <div className="demo-muted">加载日报...</div>
  if (error) return <div className="text-[var(--status-danger)]">无法加载日报，请确认后端已启动。</div>
  if (!daily) return null

  return (
    <div className="buque-page-stack">
      <PageHeader
        title="日报总览"
        subtitle={snapshotSubtitle(selectedSnapshot)}
        tooltip="仓库作用域监控指标；完成同步并分析后刷新。红灯须当天确认。"
      />

      <SectionBlock label="总览" description="当日监控规模与预警总量">
        <div className="buque-metric-grid buque-metric-grid-2">
          <MetricCard
            title="监控 SKU 总计"
            value={daily.monitored_sku_count}
            description="当日纳入仓库监控的去重 SKU 数"
            icon={Boxes}
            accent="neutral"
          />
          <MetricCard
            title="全部预警"
            value={totalAlerts}
            description="红 + 橙 + 黄业务预警行合计（不含数据异常）"
            icon={BellRing}
            accent="neutral"
            onClick={() => goAlerts({})}
          />
        </div>
      </SectionBlock>

      <SectionBlock
        label="风险等级"
        description={metricLabels?.section_descriptions.risk_levels ?? '按指标划档'}
      >
        <div className="buque-metric-grid buque-metric-grid-4">
          <MetricCard
            badge="高风险"
            value={levels.RED ?? 0}
            percent={pct(levels.RED ?? 0, totalAlerts)}
            metricLabels={metricLabels?.risk_levels.RED}
            icon={OctagonAlert}
            accent="red"
            onClick={() => goAlerts({ level: 'RED' })}
          />
          <MetricCard
            badge="中风险"
            value={levels.ORANGE ?? 0}
            percent={pct(levels.ORANGE ?? 0, totalAlerts)}
            metricLabels={metricLabels?.risk_levels.ORANGE}
            icon={TriangleAlert}
            accent="orange"
            onClick={() => goAlerts({ level: 'ORANGE' })}
          />
          <MetricCard
            badge="低风险"
            value={levels.YELLOW ?? 0}
            percent={pct(levels.YELLOW ?? 0, totalAlerts)}
            metricLabels={metricLabels?.risk_levels.YELLOW}
            icon={CircleAlert}
            accent="yellow"
            onClick={() => goAlerts({ level: 'YELLOW' })}
          />
          <MetricCard
            badge="正常"
            value={levels.GREEN ?? 0}
            metricLabels={metricLabels?.risk_levels.GREEN}
            icon={CircleCheck}
            accent="green"
            onClick={() => goAlerts({ level: 'GREEN' })}
          />
        </div>
      </SectionBlock>

      <SectionBlock
        label="专项风险"
        description={metricLabels?.section_descriptions.special_risks ?? '红橙档专项 SKU'}
      >
        <div className="buque-metric-grid buque-metric-grid-4">
          <MetricCard
            title="断货高风险"
            value={daily.stockout_high_risk_count}
            metricLabels={metricLabels?.special_risks.STOCKOUT}
            icon={PackageX}
            accent="red"
            onClick={() => goAlerts({ risk_type: 'STOCKOUT' })}
          />
          <MetricCard
            title="滞销高风险"
            value={daily.slow_moving_high_risk_count}
            metricLabels={metricLabels?.special_risks.SLOW_MOVING}
            icon={TrendingDown}
            accent="orange"
            onClick={() => goAlerts({ risk_type: 'SLOW_MOVING' })}
          />
          <MetricCard
            title="数据异常"
            value={daily.data_anomaly_count}
            description="关键字段缺失，须先修复数据再判级"
            icon={Database}
            accent="neutral"
            onClick={() => goAlerts({ risk_type: 'DATA_ANOMALY' })}
          />
        </div>
      </SectionBlock>

      <SectionBlock label="趋势" description="近 7 日走势与等级新增对比">
        {analytics && daily ? (
          <DailyTrendPanel
            trend={analytics.trend_7d}
            comparisonVsPrevDay={daily.comparison_vs_prev_day}
            comparisonVsPrevSnapshot={daily.comparison_vs_prev_snapshot}
          />
        ) : null}
      </SectionBlock>

      {analytics ? (
        <SectionBlock label="分布" description="等级与类型构成（类型为全等级计数）">
          <DistributionPanel
            levelCounts={analytics.level_counts}
            typeCounts={analytics.type_counts}
            onLevelClick={(level) => goAlerts({ level })}
            onTypeClick={(risk_type) => goAlerts({ risk_type })}
          />
        </SectionBlock>
      ) : null}
    </div>
  )
}
