import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import type { ReportAnalytics } from '#/lib/api'
import { RiskTrendChart } from '#/components/buque/ReportCharts'

function DeltaBadge({ label, value, tone }: { label: string; value: number; tone: 'red' | 'orange' }) {
  const DeltaIcon = value > 0 ? ArrowUpRight : value < 0 ? ArrowDownRight : Minus
  return (
    <div className={`buque-trend-delta buque-trend-delta-${tone}`}>
      <span className="buque-trend-delta-label">{label}</span>
      <span className="buque-trend-delta-value">
        <DeltaIcon size={14} />
        {value}
      </span>
      <span className="buque-trend-delta-hint">较昨日</span>
    </div>
  )
}

export function DailyTrendPanel({
  trend,
  newRed,
  newOrange,
}: {
  trend: ReportAnalytics['trend_7d']
  newRed: number
  newOrange: number
}) {
  return (
    <section className="buque-trend-panel">
      <div className="buque-trend-panel-head">
        <div>
          <h2 className="demo-section-title text-base">预警趋势</h2>
          <p className="mt-0.5 text-xs text-[var(--sea-ink-soft)]">近 7 日 · 仓库作用域</p>
        </div>
        <div className="buque-trend-deltas">
          <DeltaBadge label="新增红灯" value={newRed} tone="red" />
          <DeltaBadge label="新增橙灯" value={newOrange} tone="orange" />
        </div>
      </div>
      <RiskTrendChart trend={trend} embedded />
    </section>
  )
}
