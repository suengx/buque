import {
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ReportAnalytics } from '#/lib/api'
import { RISK_LEVEL_CSS } from '#/lib/risk-tokens'
import { ChartCard } from '#/components/buque/ChartCard'

const LEVEL_CHART_COLORS = {
  RED: RISK_LEVEL_CSS.RED.chart,
  ORANGE: RISK_LEVEL_CSS.ORANGE.chart,
  YELLOW: RISK_LEVEL_CSS.YELLOW.chart,
}

export function RiskTrendChart({
  trend,
  compact = false,
  embedded = false,
}: {
  trend: ReportAnalytics['trend_7d']
  compact?: boolean
  embedded?: boolean
}) {
  const data = trend.map((p) => ({
    date: p.date.slice(5),
    高风险: p.red,
    中风险: p.orange,
    低风险: p.yellow,
  }))

  const height = compact ? 200 : embedded ? 240 : 260

  const chart =
    data.length === 0 ? (
      <div className="py-10 text-center text-sm demo-muted">暂无历史监控数据</div>
    ) : (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data}>
          <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--sea-ink-soft)" />
          <YAxis tick={{ fontSize: 11 }} stroke="var(--sea-ink-soft)" width={32} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line type="monotone" dataKey="高风险" stroke={LEVEL_CHART_COLORS.RED} strokeWidth={2.5} dot={false} />
          <Line type="monotone" dataKey="中风险" stroke={LEVEL_CHART_COLORS.ORANGE} strokeWidth={2.5} dot={false} />
          <Line type="monotone" dataKey="低风险" stroke={LEVEL_CHART_COLORS.YELLOW} strokeWidth={2.5} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    )

  if (embedded) return chart

  return (
    <ChartCard title="预警趋势" subtitle="近 7 日">
      {chart}
    </ChartCard>
  )
}
