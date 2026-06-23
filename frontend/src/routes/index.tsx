import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import {
  BellRing,
  Boxes,
  CircleAlert,
  CircleCheck,
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

export const Route = createFileRoute('/')({
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
            description="红 + 橙 + 黄预警行合计，有业务含义的监控结果"
            icon={BellRing}
            accent="neutral"
            onClick={() => goAlerts({})}
          />
        </div>
      </SectionBlock>

      <SectionBlock label="风险等级" description="当日各等级预警构成与占比">
        <div className="buque-metric-grid buque-metric-grid-4">
          <MetricCard
            badge="高风险"
            value={levels.RED ?? 0}
            percent={pct(levels.RED ?? 0, totalAlerts)}
            description="须当天确认处置；规则引擎判定为紧急风险"
            icon={OctagonAlert}
            accent="red"
            onClick={() => goAlerts({ level: 'RED' })}
          />
          <MetricCard
            badge="中风险"
            value={levels.ORANGE ?? 0}
            percent={pct(levels.ORANGE ?? 0, totalAlerts)}
            description="建议责任人当日跟进确认"
            icon={TriangleAlert}
            accent="orange"
            onClick={() => goAlerts({ level: 'ORANGE' })}
          />
          <MetricCard
            badge="低风险"
            value={levels.YELLOW ?? 0}
            percent={pct(levels.YELLOW ?? 0, totalAlerts)}
            description="进入次级关注清单，定期复查"
            icon={CircleAlert}
            accent="yellow"
            onClick={() => goAlerts({ level: 'YELLOW' })}
          />
          <MetricCard
            badge="正常"
            value={levels.GREEN ?? 0}
            description="监控指标处于正常区间，无预警触发"
            icon={CircleCheck}
            accent="green"
            onClick={() => goAlerts({ level: 'GREEN' })}
          />
        </div>
      </SectionBlock>

      <SectionBlock label="专项风险" description="按业务类型聚焦的高风险 SKU">
        <div className="buque-metric-grid buque-metric-grid-2">
          <MetricCard
            title="断货高风险"
            value={daily.stockout_high_risk_count}
            description="断货类型且处于红/橙灯；红橙灯口径统计"
            icon={PackageX}
            accent="red"
            onClick={() => goAlerts({ risk_type: 'STOCKOUT' })}
          />
          <MetricCard
            title="滞销高风险"
            value={daily.slow_moving_high_risk_count}
            description="滞销类型且处于红/橙灯；红橙灯口径统计"
            icon={TrendingDown}
            accent="orange"
            onClick={() => goAlerts({ risk_type: 'SLOW_MOVING' })}
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
